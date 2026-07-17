"""Non-blocking periodic document index refresh scheduler."""

import asyncio

from app.services import DocumentIndexService


class DocumentIndexScheduler:
    """Run full document index refreshes in a worker thread at a fixed interval."""

    def __init__(
        self,
        service: DocumentIndexService,
        interval_seconds: float,
        refresh_on_startup: bool,
        enabled: bool,
    ) -> None:
        if interval_seconds <= 0:
            raise ValueError("interval_seconds must be positive")
        self._service = service
        self._interval_seconds = interval_seconds
        self._refresh_on_startup = refresh_on_startup
        self._enabled = enabled
        self._stop_event = asyncio.Event()
        self._task: asyncio.Task[None] | None = None

    @property
    def running(self) -> bool:
        """Return whether the scheduler task is active."""
        return self._task is not None and not self._task.done()

    async def start(self) -> None:
        """Start once and return without waiting for a refresh."""
        if not self._enabled or self.running:
            return
        self._stop_event.clear()
        self._task = asyncio.create_task(self._run(), name="document-index-refresh-scheduler")

    async def stop(self) -> None:
        """Signal shutdown and wait for the active refresh to finish."""
        if self._task is None:
            return
        self._stop_event.set()
        await self._task
        self._task = None

    async def _run(self) -> None:
        if self._refresh_on_startup:
            await asyncio.to_thread(self._service.refresh)
        while not self._stop_event.is_set():
            try:
                await asyncio.wait_for(
                    self._stop_event.wait(),
                    timeout=self._interval_seconds,
                )
            except TimeoutError:
                await asyncio.to_thread(self._service.refresh)
