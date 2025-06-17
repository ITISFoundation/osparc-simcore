import asyncio
import datetime
import threading
from abc import ABC, abstractmethod
from asyncio import AbstractEventLoop
from contextlib import suppress
from typing import TYPE_CHECKING, Final

from servicelib.queued_tasks.task_manager import TaskManager

if TYPE_CHECKING:
    with suppress(ImportError):
        from fastapi import FastAPI
    with suppress(ImportError):
        from aiohttp.web import Application


STARTUP_TIMEOUT: Final[float] = datetime.timedelta(minutes=1).total_seconds()


class BaseAppServer(ABC):
    def __init__(self) -> None:
        self._shutdown_event: asyncio.Event | None = None

    @property
    def fastapi_app(self) -> "FastAPI":
        raise NotImplementedError

    @property
    def aiohttp_app(self) -> "Application":
        raise NotImplementedError

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
