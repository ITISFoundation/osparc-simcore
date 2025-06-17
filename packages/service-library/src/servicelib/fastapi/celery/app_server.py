from datetime import timedelta
from typing import Final

from asgi_lifespan import LifespanManager
from fastapi import FastAPI

from ...celery.app_server import BaseAppServer

_SHUTDOWN_TIMEOUT: Final[float] = timedelta(seconds=10).total_seconds()
_STARTUP_TIMEOUT: Final[float] = timedelta(minutes=1).total_seconds()


class FastAPIAppServer(BaseAppServer):
    def __init__(self, app: FastAPI):
        super().__init__()
        self._app = app
        self._lifespan_manager: LifespanManager | None = None

    @property
    def fastapi_app(self) -> FastAPI:
        assert isinstance(self._app, FastAPI)  # nosec
        return self._app

    async def on_startup(self) -> None:
        self._lifespan_manager = LifespanManager(
            self.fastapi_app,
            startup_timeout=_STARTUP_TIMEOUT,
            shutdown_timeout=_SHUTDOWN_TIMEOUT,
        )
        await self._lifespan_manager.__aenter__()

    async def on_shutdown(self) -> None:
        if self._lifespan_manager is None:
            return
        await self._lifespan_manager.__aexit__(None, None, None)
