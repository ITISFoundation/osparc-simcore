import asyncio
import datetime
import threading
from abc import ABC, abstractmethod
from asyncio import AbstractEventLoop
from contextlib import suppress
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    with suppress(ImportError):
        from fastapi import FastAPI
    with suppress(ImportError):
        from aiohttp.web import Application


STARTUP_TIMEOUT: Final[float] = datetime.timedelta(minutes=1).total_seconds()


class BaseAppServer(ABC):
    @property
    def fastapi_app(self) -> "FastAPI":
        raise NotImplementedError

    @property
    def aiohttp_app(self) -> "Application":
        raise NotImplementedError

    @abstractmethod
    async def startup(
        self, completed_event: threading.Event, shutdown_event: asyncio.Event
    ) -> None:
        pass

    @property
    def event_loop(self) -> AbstractEventLoop:
        return self._event_loop

    @event_loop.setter
    def event_loop(self, loop: AbstractEventLoop) -> None:
        self._event_loop = loop

    @abstractmethod
    async def shutdown(self):
        pass
