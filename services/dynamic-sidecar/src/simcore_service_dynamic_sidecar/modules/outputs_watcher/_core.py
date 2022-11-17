import logging
from asyncio import CancelledError
from asyncio import Queue as AsyncQueue
from asyncio import Task, create_task, get_event_loop
from asyncio import sleep as async_sleep
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager, suppress
from multiprocessing import Queue
from pathlib import Path
from queue import Empty
from time import sleep as blocking_sleep
from typing import Generator, Optional

from fastapi import FastAPI
from servicelib.logging_utils import log_context
from watchdog.observers.api import DEFAULT_OBSERVER_TIMEOUT

from ..mounted_fs import MountedVolumes
from ..outputs_manager import OutputsManager
from ._event_filter import EventFilter
from ._observer import ObserverMonitor

logger = logging.getLogger(__name__)


class OutputsWatcher:  # pylint:disable = too-many-instance-attributes
    def __init__(
        self, *, outputs_manager: OutputsManager, path_to_observe: Path
    ) -> None:
        self.path_to_observe = path_to_observe
        self.outputs_manager = outputs_manager

        self._allow_event_propagation: bool = True
        self._task_events_worker: Optional[Task] = None
        self._task_health_worker: Optional[Task] = None

        self._events_queue: Optional[Queue] = Queue()
        self._event_filter = EventFilter(outputs_manager=outputs_manager)
        self._health_queue: AsyncQueue = AsyncQueue()
        self._observer_monitor: ObserverMonitor = ObserverMonitor(
            path_to_observe=path_to_observe,
            outputs_port_keys=outputs_manager.outputs_port_keys,
            health_queue=self._health_queue,
            events_queue=self._events_queue,
            heart_beat_interval_s=DEFAULT_OBSERVER_TIMEOUT,
        )
        self._keep_running: bool = False

    def _blocking_worker_events(self) -> None:
        self._keep_running = True
        while self._keep_running:
            blocking_sleep(DEFAULT_OBSERVER_TIMEOUT)
            if self._events_queue.qsize() == 0:
                continue
            try:
                event: Optional[str] = self._events_queue.get_nowait()
            except Empty:
                continue

            if event is None:
                continue

            if self._allow_event_propagation:
                self._event_filter.enqueue(event)

    async def _worker_events(self) -> None:
        with ThreadPoolExecutor(max_workers=1) as executror:
            await get_event_loop().run_in_executor(
                executror, self._blocking_worker_events
            )

    async def _health_check_worker(self) -> None:
        while True:
            event = await self._health_queue.get()
            if event is None:
                break

            self.outputs_manager.set_all_ports_for_upload()

    def enable_event_propagation(self) -> None:
        self._allow_event_propagation = True

    def disable_event_propagation(self) -> None:
        self._allow_event_propagation = False

    async def start(self) -> None:
        self._task_events_worker = create_task(
            self._worker_events(), name="outputs_watcher_events_worker"
        )
        self._task_health_worker = create_task(
            self._health_check_worker(), name="outputs_watcher_health_check_worker"
        )

        await self._event_filter.start()
        await self._observer_monitor.start()

        logger.info("started outputs watcher")
        await async_sleep(0.01)

    async def shutdown(self) -> None:
        """cleans up spawned tasks which might be pending"""
        with log_context(logger, logging.INFO, f"{OutputsWatcher.__name__} shutdown"):
            await self._event_filter.shutdown()
            await self._observer_monitor.stop()

            if self._task_events_worker is not None:
                # waiting for queue workers to close
                self._keep_running = False
                if self._task_events_worker is not None:
                    self._task_events_worker.cancel()
                    with suppress(CancelledError):
                        await self._task_events_worker

            if self._task_health_worker is not None:
                await self._health_queue.put(None)
                await self._task_health_worker


def setup_outputs_watcher(app: FastAPI) -> None:
    async def on_startup() -> None:
        mounted_volumes: MountedVolumes
        mounted_volumes = app.state.mounted_volumes  # nosec
        outputs_manager: OutputsManager
        outputs_manager = app.state.outputs_manager  # nosec

        app.state.outputs_watcher = OutputsWatcher(
            path_to_observe=mounted_volumes.disk_outputs_path,
            outputs_manager=outputs_manager,
        )
        app.state.outputs_watcher.disable_event_propagation()
        await app.state.outputs_watcher.start()

    async def on_shutdown() -> None:
        outputs_watcher: Optional[OutputsWatcher] = app.state.outputs_watcher
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
    disable_outputs_watcher(app)
    try:
        yield None
    finally:
        enable_outputs_watcher(app)
