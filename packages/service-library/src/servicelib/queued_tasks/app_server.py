import asyncio
import datetime
import threading
from abc import ABC, abstractmethod
from asyncio import AbstractEventLoop
from typing import Final, Generic, TypeVar

from servicelib.queued_tasks.task_manager import TaskManager

STARTUP_TIMEOUT: Final[float] = datetime.timedelta(minutes=1).total_seconds()

T = TypeVar("T")


class BaseAppServer(ABC, Generic[T]):
    def __init__(self, app: T) -> None:
        self._app: T = app
        self._shutdown_event: asyncio.Event | None = None

    @property
    def app(self) -> T:
        return self._app

    @property
    def event_loop(self) -> AbstractEventLoop:
        return self._event_loop

    @event_loop.setter
    def event_loop(self, loop: AbstractEventLoop) -> None:
        self._event_loop = loop

    @property
    def task_manager(self) -> TaskManager:
        return self._task_manager

    @task_manager.setter
    def task_manager(self, manager: TaskManager) -> None:
        self._task_manager = manager

    @abstractmethod
    async def on_startup(self) -> None:
        raise NotImplementedError

    async def startup(
        self, completed_event: threading.Event, shutdown_event: asyncio.Event
    ) -> None:
        self._shutdown_event = shutdown_event
        completed_event.set()
        await self.on_startup()
        await self._shutdown_event.wait()

    @abstractmethod
    async def on_shutdown(self) -> None:
        raise NotImplementedError

    async def shutdown(self) -> None:
        if self._shutdown_event is not None:
            self._shutdown_event.set()

        await self.on_shutdown()
