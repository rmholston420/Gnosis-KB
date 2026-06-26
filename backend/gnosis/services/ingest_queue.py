"""Document ingest queue — async worker for processing uploaded files.

Architecture
------------
A single ``IngestQueue`` instance (module-level ``ingest_queue``) manages an
``asyncio.Queue`` of ``IngestTask`` objects.  The worker coroutine runs as a
background task during the FastAPI lifespan and drains the queue sequentially.

Public API
----------
``ingest_queue.enqueue(task)`` — add a task to the queue (thread-safe).
``ingest_queue.start()``       — start the background worker (called at startup).
``ingest_queue.stop()``        — drain and stop the worker (called at shutdown).

Fix (2025-06-26)
----------------
_get_or_create_loop() created new event loops as fallback but never
registered them for close() on shutdown, causing ResourceWarning spam and
preventing clean process exit. Fix: register via atexit so loops created
in worker threads are always cleaned up when the process exits.
"""

from __future__ import annotations

import atexit
import asyncio
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class IngestTask:
    """A single document ingest job."""

    file_path: Path
    owner_id: int
    note_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.monotonic)


class IngestQueue:
    """Async ingest queue with a background worker."""

    def __init__(self) -> None:
        self._queue: asyncio.Queue[IngestTask | None] = asyncio.Queue()
        self._worker_task: asyncio.Task | None = None
        self._running = False
        self._processed = 0
        self._failed = 0
        # Track loops we created so we can close them on exit.
        self._owned_loops: list[asyncio.AbstractEventLoop] = []

    # ------------------------------------------------------------------
    # Loop helpers
    # ------------------------------------------------------------------

    def _get_or_create_loop(self) -> asyncio.AbstractEventLoop:
        """Return the running event loop, creating one if needed.

        Fix (2025-06-26): previously created new loops without registering
        them for cleanup, leaking open loop resources on process shutdown.
        New loops are now tracked in self._owned_loops and an atexit handler
        ensures they are closed when the process exits.
        """
        try:
            return asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            # Register cleanup so this loop is always closed on process exit.
            self._owned_loops.append(loop)
            atexit.register(self._close_owned_loops)
            return loop

    def _close_owned_loops(self) -> None:
        """Close all event loops created by this instance (atexit handler)."""
        for loop in self._owned_loops:
            try:
                if not loop.is_closed():
                    loop.close()
            except Exception as exc:  # noqa: BLE001
                logger.debug("Error closing owned event loop: %s", exc)
        self._owned_loops.clear()

    # ------------------------------------------------------------------
    # Queue management
    # ------------------------------------------------------------------

    def enqueue(self, task: IngestTask) -> None:
        """Add *task* to the ingest queue (thread-safe).

        Can be called from any thread. Uses ``call_soon_threadsafe`` when
        a running loop is available, otherwise falls back to direct put.
        """
        try:
            loop = asyncio.get_running_loop()
            loop.call_soon_threadsafe(self._queue.put_nowait, task)
        except RuntimeError:
            # No running loop in this thread — put directly (sync context).
            self._get_or_create_loop().run_until_complete(self._queue.put(task))

    async def start(self) -> None:
        """Start the background worker coroutine."""
        if self._running:
            return
        self._running = True
        self._worker_task = asyncio.ensure_future(self._worker())
        logger.info("IngestQueue worker started")

    async def stop(self) -> None:
        """Signal the worker to stop and wait for it to drain."""
        if not self._running:
            return
        self._running = False
        # Sentinel value tells the worker to exit after draining.
        await self._queue.put(None)
        if self._worker_task is not None:
            try:
                await asyncio.wait_for(self._worker_task, timeout=30)
            except asyncio.TimeoutError:
                logger.warning("IngestQueue worker did not stop within 30s; cancelling")
                self._worker_task.cancel()
        logger.info(
            "IngestQueue stopped. processed=%d failed=%d",
            self._processed,
            self._failed,
        )

    # ------------------------------------------------------------------
    # Background worker
    # ------------------------------------------------------------------

    async def _worker(self) -> None:
        """Drain the queue, processing one task at a time."""
        while True:
            task = await self._queue.get()
            if task is None:  # shutdown sentinel
                self._queue.task_done()
                break
            try:
                await self._process(task)
                self._processed += 1
            except Exception as exc:  # noqa: BLE001
                self._failed += 1
                logger.error(
                    "IngestQueue: task failed for %s (owner=%d): %s",
                    task.file_path,
                    task.owner_id,
                    exc,
                    exc_info=True,
                )
            finally:
                self._queue.task_done()

    async def _process(self, task: IngestTask) -> None:
        """Process a single ingest task.

        Parses the file, upserts the note to the DB, and enqueues a vector
        embedding. Delegates to ``document_parser`` and ``vault_sync``.
        """
        from gnosis.services.document_parser import parse_document
        from gnosis.services.vault_sync import _sync_file
        from gnosis.database import AsyncSessionFactory

        logger.info(
            "IngestQueue: processing %s (owner=%d)",
            task.file_path.name,
            task.owner_id,
        )

        if task.file_path.suffix.lower() == ".md":
            # Markdown files go through the standard vault sync path.
            async with AsyncSessionFactory() as db:
                result = await _sync_file(task.file_path, task.owner_id, db)
            logger.info("IngestQueue: %s", result)
        else:
            # Non-markdown: parse to text, then create/update a Note.
            parsed = await parse_document(task.file_path)
            if parsed is None:
                logger.warning(
                    "IngestQueue: unsupported file type %s — skipping",
                    task.file_path.suffix,
                )
                return

            # Build a synthetic markdown file and run through vault_sync.
            md_lines = [
                "---",
                f'title: "{parsed["title"]}"',
                f'type: source',
                f'status: processed',
                "---",
                "",
                parsed["body"],
            ]
            md_content = "\n".join(md_lines)

            # Write to a temp location inside the vault inbox.
            from gnosis.config import get_settings

            vault = Path(get_settings().vault_path)
            inbox = vault / "00-inbox"
            inbox.mkdir(parents=True, exist_ok=True)
            stem = task.file_path.stem[:200]
            md_path = inbox / f"{stem}.md"
            md_path.write_text(md_content, encoding="utf-8")

            async with AsyncSessionFactory() as db:
                result = await _sync_file(md_path, task.owner_id, db)
            logger.info("IngestQueue: %s", result)

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    @property
    def queue_size(self) -> int:
        """Number of tasks currently waiting in the queue."""
        return self._queue.qsize()

    @property
    def stats(self) -> dict[str, int]:
        """Return a dict with processed/failed/queued counts."""
        return {
            "processed": self._processed,
            "failed": self._failed,
            "queued": self.queue_size,
        }


# Module-level singleton — imported by main.py lifespan and routers.
ingest_queue = IngestQueue()
