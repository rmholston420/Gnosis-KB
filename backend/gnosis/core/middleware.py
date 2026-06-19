"""ASGI middleware collection.

RequestIDMiddleware
    Assigns a unique request-ID to every incoming request and propagates it
    on both the request (via state) and the response (via X-Request-ID header).
    This ID is also injected into every log record emitted during that request
    via a ContextVar-backed logging.Filter.

TimingMiddleware
    Adds X-Process-Time-ms to every response for quick latency observation.
"""
from __future__ import annotations

import logging
import time
import uuid
from contextvars import ContextVar
from typing import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

_request_id_var: ContextVar[str] = ContextVar("request_id", default="-")


class RequestIDFilter(logging.Filter):
    """Inject the current request_id into every log record."""

    def filter(self, record: logging.LogRecord) -> bool:  # noqa: A003
        record.request_id = _request_id_var.get("-")  # type: ignore[attr-defined]
        return True


def install_request_id_filter() -> None:
    """Attach RequestIDFilter to the root logger (call once at startup)."""
    f = RequestIDFilter()
    for handler in logging.getLogger().handlers:
        handler.addFilter(f)


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Generate + propagate a unique X-Request-ID for every request."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:  # type: ignore[override]
        req_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        token = _request_id_var.set(req_id)
        request.state.request_id = req_id
        try:
            response = await call_next(request)
        finally:
            _request_id_var.reset(token)
        response.headers["X-Request-ID"] = req_id
        return response


class TimingMiddleware(BaseHTTPMiddleware):
    """Add X-Process-Time-ms header to every response."""

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:  # type: ignore[override]
        start = time.perf_counter()
        response = await call_next(request)
        ms = round((time.perf_counter() - start) * 1000, 2)
        response.headers["X-Process-Time-Ms"] = str(ms)
        return response
