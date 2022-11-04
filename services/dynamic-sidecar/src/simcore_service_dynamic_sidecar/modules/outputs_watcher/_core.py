import asyncio
import logging
from collections import deque
from contextlib import contextmanager, suppress
from pathlib import Path
from typing import Any, Deque, Generator, Optional

from fastapi import FastAPI
from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers.api import DEFAULT_OBSERVER_TIMEOUT, BaseObserver

from ..mounted_fs import MountedVolumes
from ..outputs_manager import OutputsManager
from ._event_filter import EventFilter
from ._watchdog_extentions import ExtendedInotifyObserver

logger = logging.getLogger(__name__)


class OutputsEventHandler(FileSystemEventHandler):
    def __init__(
        self,
        path_to_observe: Path,
        outputs_manager: OutputsManager,
        event_filter: EventFilter,
    ):
        super().__init__()

        self.path_to_observe: Path = path_to_observe
        self.outputs_manager: OutputsManager = outputs_manager
        self.event_filter: EventFilter = event_filter
        self._is_enabled: bool = True
        self._background_tasks: set[asyncio.Task[Any]] = set()

    def toggle(self, *, is_enabled: bool) -> None:
        self._is_enabled = is_enabled

    def _emit_port_change_event(self, port_key: str, event: FileSystemEvent) -> None:
        if not self._is_enabled:
            return

        self.event_filter.enqueue(port_key, event)

    def on_any_event(self, event: FileSystemEvent) -> None:
        super().on_any_event(event)

        # NOTE: filtering out all events which are not relative to modifying
        # the contents of the `port_key` folders from the outputs directory

        path_relative_to_outputs = Path(event.src_path).relative_to(
            self.path_to_observe
        )

        # discard event if not part of a subfolder
        relative_path_parents = path_relative_to_outputs.parents
        event_in_subdirs = len(relative_path_parents) > 0
        if not event_in_subdirs:
            return

        # only accept events generated inside `port_key` subfolder
        possible_port_key = f"{relative_path_parents[0]}"
        if possible_port_key in self.outputs_manager.outputs_port_keys:
            self._emit_port_change_event(possible_port_key, event)


class OutputsWatcher:
    """Used to keep tack of observer threads"""

    def __init__(
        self,
        *,
        outputs_manager: OutputsManager,
    ) -> None:
        self.outputs_manager = outputs_manager

        self._observers: Deque[BaseObserver] = deque()

        self._keep_running: bool = True
        self._blocking_task: Optional[asyncio.Task] = None
        self._outputs_event_handler: Optional[OutputsEventHandler] = None

        self._event_filter = EventFilter(outputs_manager=outputs_manager)

    def observe_outputs_directory(
        self,
        path_to_observe: Path,
        recursive: bool = True,
    ) -> None:
        directory_path = path_to_observe
        path = directory_path.absolute()
        logger.debug("observing %s, %s", f"{path}", f"{recursive=}")

        self._outputs_event_handler = OutputsEventHandler(
            path_to_observe=path_to_observe,
            outputs_manager=self.outputs_manager,
            event_filter=self._event_filter,
        )
        observer = ExtendedInotifyObserver()
        observer.schedule(self._outputs_event_handler, f"{path}", recursive=recursive)
        self._observers.append(observer)

    def enable_event_propagation(self) -> None:
        if self._outputs_event_handler is not None:
            self._outputs_event_handler.toggle(is_enabled=True)

    def disable_event_propagation(self) -> None:
        if self._outputs_event_handler is not None:
            self._outputs_event_handler.toggle(is_enabled=False)

    async def _runner(self) -> None:
        try:
            for observer in self._observers:
                observer.start()

            while self._keep_running:
                # watchdog internally uses 1 sec interval to detect events
                # sleeping for less is useless.
                # If this value is bigger then the DEFAULT_OBSERVER_TIMEOUT
                # the result will not be as expected. Keep sleep to 1 second
                await asyncio.sleep(DEFAULT_OBSERVER_TIMEOUT)

        except Exception:  # pylint: disable=broad-except
            logger.exception("Watchers failed upon initialization")
        finally:
            for observer in self._observers:
                observer.stop()
                observer.join()

    async def start(self) -> None:
        if self._blocking_task is None:
            self._blocking_task = asyncio.create_task(
                self._runner(), name="blocking task"
            )
            await self._event_filter.start()
        else:
            logger.warning("Already started, will not start again")

    async def shutdown(self) -> None:
        """cleans up spawned tasks which might be pending"""

        self._keep_running = False
        if self._blocking_task is not None:
            self._blocking_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._blocking_task
            self._blocking_task = None

        await self._event_filter.shutdown()


def setup_outputs_watcher(app: FastAPI) -> None:
    async def on_startup() -> None:
        mounted_volumes: MountedVolumes
        mounted_volumes = app.state.mounted_volumes  # nosec
        outputs_manager: OutputsManager
        outputs_manager = app.state.outputs_manager  # nosec

        app.state.outputs_watcher = OutputsWatcher(outputs_manager=outputs_manager)
        app.state.outputs_watcher.observe_outputs_directory(
            mounted_volumes.disk_outputs_path
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
