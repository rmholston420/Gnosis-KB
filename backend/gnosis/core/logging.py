"""Structured JSON logging configuration.

Configures uvicorn + application loggers to emit structured JSON lines
suitable for log aggregators (Loki, Datadog, CloudWatch).
When LOG_FORMAT=text (default in dev), falls back to human-readable output.
Every log line emitted inside a request will carry a `request_id` field
(populated by RequestIDFilter installed at startup).
"""

from __future__ import annotations

import json
import logging
import sys
from typing import Any

from gnosis.config import settings


class JSONFormatter(logging.Formatter):
    """Emit log records as single-line JSON objects."""

    def format(self, record: logging.LogRecord) -> str:  # noqa: A003
        log_obj: dict[str, Any] = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "request_id": getattr(record, "request_id", "-"),
            "msg": record.getMessage(),
        }
        if record.exc_info:
            log_obj["exc"] = self.formatException(record.exc_info)
        return json.dumps(log_obj)


def configure_logging() -> None:
    """Set up root logger with JSON or text formatting based on LOG_FORMAT env var."""
    level = getattr(logging, settings.log_level.upper(), logging.INFO)
    handler = logging.StreamHandler(sys.stdout)
    if getattr(settings, "log_format", "text") == "json":
        handler.setFormatter(JSONFormatter())
    else:
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)-8s [%(request_id)s] %(name)s — %(message)s")
        )
    root = logging.getLogger()
    root.setLevel(level)
    root.handlers = [handler]
    # Silence noisy third-party loggers
    for lib in ("watchdog", "sqlalchemy.engine", "httpx", "httpcore"):
        logging.getLogger(lib).setLevel(logging.WARNING)
