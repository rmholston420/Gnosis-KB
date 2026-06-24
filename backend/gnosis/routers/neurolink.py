"""
Neurolink Router — /api/v1/neurolink

Endpoints:
  GET  /stream   — SSE stream placeholder (returns a single status event then closes)

This stub silences the 404 spam from the frontend while the full
Neurolink feature is built out.
"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncGenerator

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/neurolink", tags=["neurolink"])


@router.get("/stream", summary="Neurolink SSE stream (stub)")
async def neurolink_stream() -> StreamingResponse:
    """Server-Sent Events endpoint for Neurolink.

    Currently returns a single 'status' event indicating the feature is
    not yet implemented, then closes the stream.
    """

    async def _events() -> AsyncGenerator[str, None]:
        yield f"data: {json.dumps({'status': 'not_implemented', 'message': 'Neurolink is coming soon.'})}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(_events(), media_type="text/event-stream")
