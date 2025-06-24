from asgi_lifespan import LifespanManager
from fastapi import FastAPI

from ...celery.app_server import BaseAppServer


class FastAPIAppServer(BaseAppServer[FastAPI]):
    def __init__(self, app: FastAPI):
        super().__init__(app)
        self._lifespan_manager: LifespanManager | None = None

    async def on_startup(self) -> None:
        self._lifespan_manager = LifespanManager(
            self.app,
            startup_timeout=None,  # waits for full app initialization (DB migrations, etc.)
            shutdown_timeout=None,
        )
        await self._lifespan_manager.__aenter__()

    async def on_shutdown(self) -> None:
        if self._lifespan_manager is None:
            return
        await self._lifespan_manager.__aexit__(None, None, None)
