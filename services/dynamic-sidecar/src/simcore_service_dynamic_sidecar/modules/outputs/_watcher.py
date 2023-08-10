import logging
from asyncio import CancelledError, Task, create_task
from collections.abc import Generator
from contextlib import contextmanager, suppress

from fastapi import FastAPI
from servicelib.logging_utils import log_context
from watchdog.observers.api import DEFAULT_OBSERVER_TIMEOUT

from ._context import OutputsContext
from ._event_filter import EventFilter
from ._event_handler import EventHandlerObserver
from ._manager import OutputsManager

logger = logging.getLogger(__name__)


class OutputsWatcher:
    def __init__(
        self, *, outputs_manager: OutputsManager, outputs_context: OutputsContext
    ) -> None:
        self.outputs_manager = outputs_manager
        self.outputs_context = outputs_context

        self._allow_event_propagation: bool = False
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

            if self._allow_event_propagation:
                await self._event_filter.enqueue(event)

    def enable_event_propagation(self) -> None:
        self._allow_event_propagation = True

    def disable_event_propagation(self) -> None:
        self._allow_event_propagation = False

    async def start(self) -> None:
        with log_context(logger, logging.INFO, f"{OutputsWatcher.__name__} start"):
            self._task_events_worker = create_task(
                self._worker_events(), name="outputs_watcher_events_worker"
            )

            await self._event_filter.start()
            await self._observer_monitor.start()

    async def shutdown(self) -> None:
        """cleans up spawned tasks which might be pending"""
        with log_context(logger, logging.INFO, f"{OutputsWatcher.__name__} shutdown"):
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
        disable_outputs_watcher(app)

    async def on_shutdown() -> None:
        outputs_watcher: OutputsWatcher | None = app.state.outputs_watcher
        if outputs_watcher is not None:
            await outputs_watcher.shutdown()

    app.add_event_handler("startup", on_startup)
    app.add_event_handler("shutdown", on_shutdown)


def disable_outputs_watcher(app: FastAPI) -> None:
    if app.state.outputs_watcher is not None:
        app.state.outputs_watcher.disable_event_propagation()


def enable_outputs_watcher(app: FastAPI) -> None:
    if app.state.outputs_watcher is not None:
        app.state.outputs_watcher.enable_event_propagation()


@contextmanager
def outputs_watcher_disabled(app: FastAPI) -> Generator[None, None, None]:
    try:
        disable_outputs_watcher(app)
        yield None
    finally:
        enable_outputs_watcher(app)
