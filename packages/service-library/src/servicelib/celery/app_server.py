import asyncio
import threading
from abc import ABC, abstractmethod
from asyncio import AbstractEventLoop
from typing import Generic, TypeVar

from ..celery.task_manager import TaskManager

T = TypeVar("T")


class BaseAppServer(ABC, Generic[T]):
    def __init__(self, app: T) -> None:
        self._app: T = app
        self._shutdown_event: asyncio.Event = asyncio.Event()

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
    def shutdown_event(self) -> asyncio.Event:
        return self._shutdown_event

    @property
    def task_manager(self) -> TaskManager:
        return self._task_manager

    @task_manager.setter
    def task_manager(self, manager: TaskManager) -> None:
        self._task_manager = manager

    @abstractmethod
    async def lifespan(
        self,
        startup_completed_event: threading.Event,
    ) -> None:
        raise NotImplementedError
