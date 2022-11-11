import asyncio
import functools
import logging
import time
from asyncio import AbstractEventLoop
from collections import deque
from contextlib import contextmanager
from os import name
from pathlib import Path
from typing import Any, Awaitable, Callable, Deque, Generator, Optional

from fastapi import FastAPI
from servicelib.utils import logged_gather
from simcore_sdk.node_ports_common.file_io_utils import LogRedirectCB
from simcore_service_dynamic_sidecar.modules import nodeports
from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers.api import BaseObserver

from ...core.rabbitmq import post_sidecar_log_message
from ..mounted_fs import MountedVolumes
from ._watchdog_extentions import ExtendedInotifyObserver

DETECTION_INTERVAL: float = 1.0
TASK_NAME_FOR_CLEANUP = f"{name}.InvokeTask"

logger = logging.getLogger(__name__)


class AsyncLockedFloat:
    __slots__ = ("_lock", "_value")

    def __init__(self, initial_value: Optional[float] = None):
        self._lock = asyncio.Lock()
        self._value: Optional[float] = initial_value

    async def set_value(self, value: float) -> None:
        async with self._lock:
            self._value = value

    async def get_value(self) -> Optional[float]:
        async with self._lock:
            return self._value


def async_run_once_after_event_chain(
    detection_interval: float,
):
    """
    The function's call is delayed by a period equal to the
    `detection_interval` and multiple calls during this
    interval will be ignored and will reset the delay.

    param: detection_interval the amount of time between
    returns: decorator to be applied to async functions
    """

    def internal(decorated_function: Callable[..., Awaitable[Any]]):
        last = AsyncLockedFloat(initial_value=None)

        @functools.wraps(decorated_function)
        async def wrapper(*args: Any, **kwargs: Any):
            # skipping  the first time the event chain starts
            if await last.get_value() is None:
                await last.set_value(time.time())
                return None

            await last.set_value(time.time())

            last_read = await last.get_value()
            await asyncio.sleep(detection_interval)

            if last_read == await last.get_value():
                return await decorated_function(*args, **kwargs)

            return None

        return wrapper

    return internal


async def _push_directory(
    directory_path: Path, io_log_redirect_cb: Optional[LogRedirectCB]
) -> None:
    await nodeports.dispatch_update_for_directory(
        directory_path, io_log_redirect_cb=io_log_redirect_cb
    )


@async_run_once_after_event_chain(detection_interval=DETECTION_INTERVAL)
async def _push_directory_after_event_chain(
    directory_path: Path, io_log_redirect_cb: Optional[LogRedirectCB]
) -> None:
    await _push_directory(directory_path, io_log_redirect_cb=io_log_redirect_cb)


def async_push_directory(
    event_loop: AbstractEventLoop,
    directory_path: Path,
    tasks_collection: set[asyncio.Task[Any]],
    io_log_redirect_cb: Optional[LogRedirectCB],
) -> None:
    task = event_loop.create_task(
        _push_directory_after_event_chain(directory_path, io_log_redirect_cb),
        name=TASK_NAME_FOR_CLEANUP,
    )
    tasks_collection.add(task)
    task.add_done_callback(tasks_collection.discard)


class UnifyingEventHandler(FileSystemEventHandler):
    def __init__(
        self,
        loop: AbstractEventLoop,
        directory_path: Path,
        io_log_redirect_cb: Optional[LogRedirectCB],
    ):
        super().__init__()

        self.loop: AbstractEventLoop = loop
        self.directory_path: Path = directory_path
        self._is_enabled: bool = True
        self._background_tasks: set[asyncio.Task[Any]] = set()
        self.io_log_redirect_cb: Optional[LogRedirectCB] = io_log_redirect_cb

    def set_enabled(self, is_enabled: bool) -> None:
        self._is_enabled = is_enabled

    def _invoke_push_directory(self) -> None:
        if not self._is_enabled:
            return

        async_push_directory(
            self.loop,
            self.directory_path,
            self._background_tasks,
            self.io_log_redirect_cb,
        )

    def on_any_event(self, event: FileSystemEvent) -> None:
        super().on_any_event(event)
        self._invoke_push_directory()


class DirectoryWatcherObservers:
    """Used to keep tack of observer threads"""

    def __init__(self, *, io_log_redirect_cb: Optional[LogRedirectCB]) -> None:
        self._observers: Deque[BaseObserver] = deque()

        self._keep_running: bool = True
        self._blocking_task: Optional[Awaitable[Any]] = None
        self.outputs_event_handle: Optional[UnifyingEventHandler] = None
        self.io_log_redirect_cb: Optional[LogRedirectCB] = io_log_redirect_cb

    def observe_directory(self, directory_path: Path, recursive: bool = True) -> None:
        logger.debug("observing %s, %s", f"{directory_path=}", f"{recursive=}")
        path = directory_path.absolute()
        self.outputs_event_handle = UnifyingEventHandler(
            loop=asyncio.get_event_loop(),
            directory_path=path,
            io_log_redirect_cb=self.io_log_redirect_cb,
        )
        observer = ExtendedInotifyObserver()
        observer.schedule(self.outputs_event_handle, str(path), recursive=recursive)
        self._observers.append(observer)

    def enable_event_propagation(self) -> None:
        if self.outputs_event_handle is not None:
            self.outputs_event_handle.set_enabled(True)

    def disable_event_propagation(self) -> None:
        if self.outputs_event_handle is not None:
            self.outputs_event_handle.set_enabled(False)

    async def _runner(self) -> None:
        try:
            for observer in self._observers:
                observer.start()

            while self._keep_running:
                # watchdog internally uses 1 sec interval to detect events
                # sleeping for less is useless.
                # If this value is bigger then the DETECTION_INTERVAL
                # the result will not be as expected. Keep sleep to 1 second
                await asyncio.sleep(1)

        except Exception:  # pylint: disable=broad-except
            logger.exception("Watchers failed upon initialization")
        finally:
            for observer in self._observers:
                observer.stop()
                observer.join()

    def start(self) -> None:
        if self._blocking_task is None:
            self._blocking_task = asyncio.create_task(
                self._runner(), name="blocking task"
            )
        else:
            logger.warning("Already started, will not start again")

    async def stop(self) -> None:
        """cleans up spawned tasks which might be pending"""
        self._keep_running = False
        if self._blocking_task:
            try:
                await self._blocking_task
                self._blocking_task = None
            except asyncio.CancelledError:
                logger.info("Task was already cancelled")

            # cleanup pending tasks to avoid errors
            tasks_to_await: Deque[Awaitable[Any]] = deque()
            for task in asyncio.all_tasks():
                if task.get_name() == TASK_NAME_FOR_CLEANUP:
                    tasks_to_await.append(task)

            # awaiting pending spawned tasks will not raise warnings
            await logged_gather(*tasks_to_await)


def setup_directory_watcher(app: FastAPI) -> None:
    async def on_startup() -> None:
        mounted_volumes: MountedVolumes
        mounted_volumes = app.state.mounted_volumes  # nosec
        io_log_redirect_cb = None
        if app.state.settings.RABBIT_SETTINGS:
            io_log_redirect_cb = functools.partial(post_sidecar_log_message, app)
        logger.debug(
            "setting up directory watcher %s",
            "with redirection of logs..." if io_log_redirect_cb else "...",
        )
        app.state.dir_watcher = DirectoryWatcherObservers(
            io_log_redirect_cb=io_log_redirect_cb
        )
        app.state.dir_watcher.observe_directory(mounted_volumes.disk_outputs_path)
        app.state.dir_watcher.disable_event_propagation()
        app.state.dir_watcher.start()

    async def on_shutdown() -> None:
        if app.state.dir_watcher is not None:
            await app.state.dir_watcher.stop()

    app.add_event_handler("startup", on_startup)
    app.add_event_handler("shutdown", on_shutdown)


def disable_directory_watcher(app: FastAPI) -> None:
    if app.state.dir_watcher is not None:
        app.state.dir_watcher.disable_event_propagation()


def enable_directory_watcher(app: FastAPI) -> None:
    if app.state.dir_watcher is not None:
        app.state.dir_watcher.enable_event_propagation()


@contextmanager
def directory_watcher_disabled(app: FastAPI) -> Generator[None, None, None]:
    disable_directory_watcher(app)
    try:
        yield None
    finally:
        enable_directory_watcher(app)
