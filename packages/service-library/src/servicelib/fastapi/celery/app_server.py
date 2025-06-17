import asyncio
import threading
from datetime import timedelta
from typing import Final

from asgi_lifespan import LifespanManager
from fastapi import FastAPI

from ...celery.app_server import BaseAppServer

_SHUTDOWN_TIMEOUT: Final[float] = timedelta(seconds=10).total_seconds()
_STARTUP_TIMEOUT: Final[float] = timedelta(minutes=1).total_seconds()


class FastAPIAppServer(BaseAppServer):
    def __init__(self, app: FastAPI):
        self._app = app
        self._lifespan_manager: LifespanManager | None = None
        self._shutdown_event: asyncio.Event | None = None

    @property
    def fastapi_app(self) -> FastAPI:
        assert isinstance(self._app, FastAPI)  # nosec
        return self._app

    async def startup(
        self, completed_event: threading.Event, shutdown_event: asyncio.Event
    ):
        self._lifespan_manager = LifespanManager(
            self.fastapi_app,
            startup_timeout=_STARTUP_TIMEOUT,
            shutdown_timeout=_SHUTDOWN_TIMEOUT,
        )
        self._shutdown_event = shutdown_event
        await self._lifespan_manager.__aenter__()
        completed_event.set()
        await self._shutdown_event.wait()

    async def shutdown(self):
        if self._shutdown_event is not None:
            self._shutdown_event.set()

        if self._lifespan_manager is None:
            return
        await self._lifespan_manager.__aexit__(None, None, None)
