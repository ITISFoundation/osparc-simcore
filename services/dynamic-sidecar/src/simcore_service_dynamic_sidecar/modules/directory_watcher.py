import asyncio
import logging
import time
from asyncio import AbstractEventLoop
from collections import deque
from functools import wraps
from os import name
from pathlib import Path
from typing import Any, Awaitable, Callable, Deque, Optional

from fastapi import FastAPI
from servicelib.utils import logged_gather
from simcore_service_dynamic_sidecar.modules.nodeports import (
    dispatch_update_for_directory,
)
from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from .mounted_fs import MountedVolumes, setup_mounted_fs

DETECTION_INTERVAL: float = 1.0
TASK_NAME_FOR_CLEANUP = f"{name}.InvokeTask"

logger = logging.getLogger(__name__)

_dir_watcher: Optional["DirectoryWatcherObservers"] = None


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
) -> Callable[[Any], Optional[Any]]:
    """
    The function's call is delayed by a period equal to the
    `detection_interval` and multiple calls during this
    interval will be ignored and will reset the delay.

    param: detection_interval the amount of time between
    returns: decorator to be applied to async functions
    """

    def internal(
        decorated_function: Callable[[Any], Optional[Any]]
    ) -> Callable[[Any], Optional[Any]]:
        last = AsyncLockedFloat(initial_value=None)

        @wraps(decorated_function)
        async def wrapper(*args: Any, **kwargs: Any) -> Optional[Any]:
            # skipping  the first time the event chain starts
            if await last.get_value() is None:
                await last.set_value(time.time())
                return None

            await last.set_value(time.time())

            last_read = await last.get_value()
            await asyncio.sleep(detection_interval)

            if last_read == await last.get_value():
                return await decorated_function(*args, **kwargs)  # type: ignore

            return None

        return wrapper

    return internal


async def push_directory_via_nodeports(directory_path: Path) -> None:
    await dispatch_update_for_directory(directory_path)


@async_run_once_after_event_chain(detection_interval=DETECTION_INTERVAL)
async def invoke_push_directory_via_nodeports(directory_path: Path) -> None:
    await push_directory_via_nodeports(directory_path)


def trigger_async_invoke_push_mapped_data(
    loop: AbstractEventLoop, directory_path: Path
) -> None:
    loop.create_task(
        invoke_push_directory_via_nodeports(directory_path), name=TASK_NAME_FOR_CLEANUP
    )


class UnifyingEventHandler(FileSystemEventHandler):
    def __init__(self, loop: AbstractEventLoop, directory_path: Path):
        super().__init__()

        self.loop: AbstractEventLoop = loop
        self.directory_path: Path = directory_path

    def on_any_event(self, event: FileSystemEvent) -> None:
        super().on_any_event(event)
        trigger_async_invoke_push_mapped_data(self.loop, self.directory_path)


class DirectoryWatcherObservers:
    """Used to keep tack of observer threads"""

    def __init__(
        self,
    ) -> None:
        self._observers: Deque[Observer] = deque()

        self._keep_running: bool = True
        self._blocking_task: Optional[Awaitable[Any]] = None

    def observe_directory(self, directory_path: Path, recursive: bool = True) -> None:
        path = directory_path.absolute()
        outputs_event_handle = UnifyingEventHandler(
            loop=asyncio.get_event_loop(), directory_path=path
        )
        observer = Observer()
        observer.schedule(outputs_event_handle, str(path), recursive=recursive)
        self._observers.append(observer)

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
        global _dir_watcher  # pylint: disable=global-statement

        mounted_volumes: MountedVolumes = setup_mounted_fs()

        _dir_watcher = DirectoryWatcherObservers()
        _dir_watcher.observe_directory(mounted_volumes.disk_outputs_path)
        _dir_watcher.start()

    async def on_shutdown() -> None:
        if _dir_watcher is not None:
            await _dir_watcher.stop()

    app.add_event_handler("startup", on_startup)
    app.add_event_handler("shutdown", on_shutdown)


__all__ = ["setup_directory_watcher"]
