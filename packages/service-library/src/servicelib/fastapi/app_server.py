import asyncio
import threading
from datetime import timedelta
from typing import Final

from asgi_lifespan import LifespanManager
from fastapi import FastAPI

from ..base_app_server import BaseAppServer

_SHUTDOWN_TIMEOUT: Final[float] = timedelta(seconds=10).total_seconds()
_STARTUP_TIMEOUT: Final[float] = timedelta(minutes=1).total_seconds()


class FastAPIAppServer(BaseAppServer):
    def __init__(self, app: FastAPI):
        self._app = app
        self._lifespan_manager: LifespanManager | None = None
        self._shutdown_event = asyncio.Event()

    @property
    def fastapi_app(self) -> FastAPI:
        assert isinstance(self._app, FastAPI)  # nosec
        return self._app

    async def startup(self, completed: threading.Event):
        self._lifespan_manager = LifespanManager(
            self.fastapi_app,
            startup_timeout=_STARTUP_TIMEOUT,
            shutdown_timeout=_SHUTDOWN_TIMEOUT,
        )
        await self._lifespan_manager.__aenter__()
        completed.set()
        await self._shutdown_event.wait()

    async def shutdown(self):
        self._shutdown_event.set()
        if self._lifespan_manager is None:
            return
        await self._lifespan_manager.__aexit__(None, None, None)
