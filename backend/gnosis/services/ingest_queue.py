"""
LightRAG Bulk Ingest Queue (Priority 4)
========================================
Replaces the previous fire-and-forget pattern for large vault ingestions with
an async task queue backed by ``asyncio.Queue``.  This ensures:

1. Large vault syncs do not block the FastAPI event loop.
2. Workers process files one-at-a-time (configurable ``_MAX_WORKERS``) so
   Qdrant / LightRAG are not overwhelmed.
3. Failed tasks are retried up to ``_MAX_RETRIES`` times with exponential
   back-off before being sent to a dead-letter log.
4. Progress events are emitted on the ``vault_events`` WebSocket so the UI
   shows a live ingest progress bar without polling.

Architecture
------------
The queue starts automatically during the FastAPI lifespan alongside the
watchdog observer::

    # main.py lifespan
    ingest_queue = IngestQueue()
    await ingest_queue.start()
    yield
    await ingest_queue.stop()

Files / notes are enqueued by:
- ``vault_sync.run_full_sync_for_user()`` (full resync)
- ``ingest.py`` endpoints (single-file ingest)

Task shape
----------
Each task is an ``IngestTask`` dataclass::

    IngestTask(path=Path(...), owner_id=42, retry=0)

Public API
----------
    queue = get_ingest_queue()   # module-level singleton
    await queue.enqueue(IngestTask(path=p, owner_id=uid))
    await queue.start()
    await queue.stop()
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

_MAX_WORKERS: int = 2  # parallel worker coroutines draining the queue
_MAX_RETRIES: int = 3  # per-task retry limit before dead-letter
_RETRY_BASE_DELAY: float = 2.0  # seconds; doubled each retry
_QUEUE_MAX_SIZE: int = 5000  # cap to prevent unbounded memory growth


# ---------------------------------------------------------------------------
# Task
# ---------------------------------------------------------------------------


@dataclass
class IngestTask:
    """A single file to sync into DB + vector store.

    Attributes
    ----------
    path:
        Absolute path to the ``.md`` file in the vault.
    owner_id:
        The user ID to stamp on DB rows created or updated from this file.
    retry:
        Current retry count.  Workers increment this and re-enqueue on failure
        until the limit is reached.
    """

    path: Path
    owner_id: int
    retry: int = 0


# ---------------------------------------------------------------------------
# Queue
# ---------------------------------------------------------------------------


class IngestQueue:
    """Async task queue that drains into vault_sync._sync_file().

    Thread-safety
    -------------
    All public methods are coroutines and must be called from the same event
    loop that the FastAPI app runs on.  The watchdog observer runs in a thread;
    it should use :meth:`enqueue_threadsafe` instead of :meth:`enqueue`.

    Usage
    -----
    ::

        queue = IngestQueue()
        await queue.start()

        # From async code
        await queue.enqueue(IngestTask(path=p, owner_id=1))

        # From watchdog thread
        queue.enqueue_threadsafe(IngestTask(path=p, owner_id=1))

        await queue.stop()
    """

    def __init__(
        self,
        max_workers: int = _MAX_WORKERS,
        max_size: int = _QUEUE_MAX_SIZE,
    ) -> None:
        self._queue: asyncio.Queue[IngestTask] = asyncio.Queue(maxsize=max_size)
        self._max_workers = max_workers
        self._workers: list[asyncio.Task[None]] = []
        self._running = False
        self._processed = 0
        self._failed = 0

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Spawn worker coroutines.  Call once during app startup."""
        if self._running:
            return
        self._running = True
        self._workers = [
            asyncio.create_task(self._worker(i), name=f"ingest-worker-{i}")
            for i in range(self._max_workers)
        ]
        logger.info(
            "IngestQueue started with %d workers (queue_max=%d)",
            self._max_workers,
            self._queue.maxsize,
        )

    async def stop(self) -> None:
        """Drain the queue then cancel workers.  Call during app shutdown."""
        if not self._running:
            return
        # Signal workers to stop after draining
        for _ in self._workers:
            await self._queue.put(_SENTINEL)  # type: ignore[arg-type]
        # Give workers time to flush
        await asyncio.gather(*self._workers, return_exceptions=True)
        self._running = False
        logger.info(
            "IngestQueue stopped. processed=%d failed=%d",
            self._processed,
            self._failed,
        )

    # ------------------------------------------------------------------
    # Enqueue
    # ------------------------------------------------------------------

    async def enqueue(self, task: IngestTask) -> None:
        """Add a task to the queue.  Drops silently if the queue is full."""
        if not self._running:
            logger.warning("IngestQueue not started; dropping task %s", task.path.name)
            return
        try:
            self._queue.put_nowait(task)
        except asyncio.QueueFull:
            logger.warning(
                "IngestQueue full (%d items); dropping %s",
                self._queue.qsize(),
                task.path.name,
            )

    def enqueue_threadsafe(
        self,
        task: IngestTask,
        loop: asyncio.AbstractEventLoop | None = None,
    ) -> None:
        """Thread-safe variant for use from watchdog observer threads.

        Uses asyncio.get_running_loop() (Python 3.10+) which raises RuntimeError
        if called outside a running event loop. The loop parameter allows callers
        to pass an explicit loop reference (e.g. captured during startup) which
        is the recommended pattern for watchdog thread callbacks.
        """
        try:
            _loop = loop or asyncio.get_running_loop()
        except RuntimeError:
            # No running loop in this thread — caller must supply one explicitly.
            raise RuntimeError(
                "enqueue_threadsafe called from a thread with no running event loop. "
                "Pass the app event loop explicitly: queue.enqueue_threadsafe(task, loop=app_loop)"
            )
        _loop.call_soon_threadsafe(self._queue.put_nowait, task)

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    @property
    def qsize(self) -> int:
        """Current number of pending tasks."""
        return self._queue.qsize()

    @property
    def processed(self) -> int:
        """Total tasks successfully processed since startup."""
        return self._processed

    @property
    def failed(self) -> int:
        """Total tasks that exhausted retries since startup."""
        return self._failed

    # ------------------------------------------------------------------
    # Worker
    # ------------------------------------------------------------------

    async def _worker(self, worker_id: int) -> None:
        """Internal worker coroutine — drains the queue continuously."""
        from gnosis.database import AsyncSessionFactory
        from gnosis.services.vault_sync import _sync_file

        logger.debug("[ingest-worker-%d] started", worker_id)

        while True:
            task = await self._queue.get()

            # Sentinel signals graceful shutdown
            if task is _SENTINEL:  # type: ignore[comparison-overlap]
                self._queue.task_done()
                break

            try:
                async with AsyncSessionFactory() as db:
                    result = await _sync_file(task.path, task.owner_id, db)
                    logger.debug("[ingest-worker-%d] %s", worker_id, result)
                self._processed += 1
                self._emit_progress(task, success=True)

            except Exception as exc:  # noqa: BLE001
                if task.retry < _MAX_RETRIES:
                    delay = _RETRY_BASE_DELAY * (2**task.retry)
                    logger.warning(
                        "[ingest-worker-%d] retry %d/%d in %.1fs for %s: %s",
                        worker_id,
                        task.retry + 1,
                        _MAX_RETRIES,
                        delay,
                        task.path.name,
                        exc,
                    )
                    await asyncio.sleep(delay)
                    await self.enqueue(
                        IngestTask(
                            path=task.path,
                            owner_id=task.owner_id,
                            retry=task.retry + 1,
                        )
                    )
                else:
                    self._failed += 1
                    self._emit_progress(task, success=False, error=str(exc))
                    logger.error(
                        "[ingest-worker-%d] dead-letter %s after %d retries: %s",
                        worker_id,
                        task.path.name,
                        _MAX_RETRIES,
                        exc,
                    )
            finally:
                self._queue.task_done()

        logger.debug("[ingest-worker-%d] stopped", worker_id)

    # ------------------------------------------------------------------
    # WebSocket progress events
    # ------------------------------------------------------------------

    def _emit_progress(
        self,
        task: IngestTask,
        *,
        success: bool,
        error: str = "",
    ) -> None:
        """Broadcast a progress event on the vault WebSocket channel.

        Fixed: was importing from gnosis.routers.vault_ws (non-existent module).
        Corrected to gnosis.routers.ws where broadcast_vault_event lives.

        Non-fatal — if the WebSocket manager is unavailable, the event
        is logged and dropped.
        """
        try:
            import asyncio

            from gnosis.routers.ws import broadcast_vault_event

            event = {
                "type": "ingest_progress",
                "path": str(task.path.name),
                "owner_id": task.owner_id,
                "success": success,
                "error": error,
                "queue_size": self._queue.qsize(),
                "processed": self._processed,
                "failed": self._failed,
            }
            asyncio.create_task(broadcast_vault_event(event))
        except ImportError:
            pass  # ws router not yet wired up — no-op
        except Exception as exc:  # noqa: BLE001
            logger.debug("_emit_progress failed: %s", exc)


# ---------------------------------------------------------------------------
# Sentinel (used to signal workers to stop)
# ---------------------------------------------------------------------------

_SENTINEL = object()


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_queue_instance: IngestQueue | None = None


def get_ingest_queue() -> IngestQueue:
    """Return the module-level IngestQueue singleton.

    The singleton is created lazily on first call.  In tests, create a fresh
    ``IngestQueue()`` directly rather than using this function to avoid
    cross-test state bleed.
    """
    global _queue_instance  # noqa: PLW0603
    if _queue_instance is None:
        _queue_instance = IngestQueue()
    return _queue_instance
