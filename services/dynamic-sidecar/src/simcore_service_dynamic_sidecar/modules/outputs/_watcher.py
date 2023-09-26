import logging
from asyncio import CancelledError, Task, create_task
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI
from servicelib.logging_utils import log_context
from watchdog.observers.api import DEFAULT_OBSERVER_TIMEOUT

from ._context import OutputsContext
from ._event_filter import EventFilter
from ._event_handler import EventHandlerObserver
from ._manager import OutputsManager

_logger = logging.getLogger(__name__)


class OutputsWatcher:
    def __init__(
        self, *, outputs_manager: OutputsManager, outputs_context: OutputsContext
    ) -> None:
        self.outputs_manager = outputs_manager
        self.outputs_context = outputs_context

        self._task_events_worker: Task | None = None
        self._event_filter = EventFilter(outputs_manager=outputs_manager)
        self._observer_monitor: EventHandlerObserver = EventHandlerObserver(
            outputs_context=self.outputs_context,
            outputs_manager=self.outputs_manager,
            heart_beat_interval_s=DEFAULT_OBSERVER_TIMEOUT,
        )

    async def _worker_events(self) -> None:
        while True:
            event: str | None = (
                await self.outputs_context.port_key_events_queue.coro_get()
            )
            if event is None:
                break

            await self._event_filter.enqueue(event)

    async def enable_event_propagation(self) -> None:
        await self.outputs_context.toggle_event_propagation(is_enabled=True)

    async def disable_event_propagation(self) -> None:
        await self.outputs_context.toggle_event_propagation(is_enabled=False)

    async def start(self) -> None:
        with log_context(_logger, logging.INFO, f"{OutputsWatcher.__name__} start"):
            self._task_events_worker = create_task(
                self._worker_events(), name="outputs_watcher_events_worker"
            )

            await self._event_filter.start()
            await self._observer_monitor.start()

    async def shutdown(self) -> None:
        """cleans up spawned tasks which might be pending"""
        with log_context(_logger, logging.INFO, f"{OutputsWatcher.__name__} shutdown"):
            await self._event_filter.shutdown()
            await self._observer_monitor.stop()

            if self._task_events_worker is not None:
                self._task_events_worker.cancel()
                with suppress(CancelledError):
                    await self._task_events_worker


def setup_outputs_watcher(app: FastAPI) -> None:
    async def on_startup() -> None:
        assert isinstance(app.state.outputs_context, OutputsContext)  # nosec
        outputs_context: OutputsContext = app.state.outputs_context
        outputs_manager: OutputsManager
        outputs_manager = app.state.outputs_manager  # nosec

        app.state.outputs_watcher = OutputsWatcher(
            outputs_manager=outputs_manager,
            outputs_context=outputs_context,
        )
        await app.state.outputs_watcher.start()
        await disable_event_propagation(app)

    async def on_shutdown() -> None:
        outputs_watcher: OutputsWatcher | None = app.state.outputs_watcher
        if outputs_watcher is not None:
            await outputs_watcher.shutdown()

    app.add_event_handler("startup", on_startup)
    app.add_event_handler("shutdown", on_shutdown)


async def disable_event_propagation(app: FastAPI) -> None:
    outputs_watcher: OutputsWatcher | None = app.state.outputs_watcher
    if outputs_watcher is not None:
        await outputs_watcher.disable_event_propagation()


async def enable_event_propagation(app: FastAPI) -> None:
    outputs_watcher: OutputsWatcher | None = app.state.outputs_watcher
    if outputs_watcher is not None:
        await outputs_watcher.enable_event_propagation()


@asynccontextmanager
async def event_propagation_disabled(app: FastAPI) -> AsyncGenerator[None, None]:
    try:
        await disable_event_propagation(app)
        yield None
    finally:
        await enable_event_propagation(app)
