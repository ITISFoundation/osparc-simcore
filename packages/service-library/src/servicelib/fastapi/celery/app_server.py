import datetime
import logging
import threading
from typing import Final

from asgi_lifespan import LifespanManager
from fastapi import FastAPI

from ...celery.app_server import BaseAppServer

_SHUTDOWN_TIMEOUT: Final[float] = datetime.timedelta(seconds=10).total_seconds()

_logger = logging.getLogger(__name__)


class FastAPIAppServer(BaseAppServer[FastAPI]):
    def __init__(self, app: FastAPI):
        super().__init__(app)
        self._lifespan_manager: LifespanManager | None = None

    async def lifespan(self, startup_completed_event: threading.Event) -> None:
        async with LifespanManager(
            self.app,
            startup_timeout=None,  # waits for full app initialization (DB migrations, etc.)
            shutdown_timeout=_SHUTDOWN_TIMEOUT,
        ):
            _logger.info("fastapi app initialized")
            startup_completed_event.set()
            await self.shutdown_event.wait()  # NOTE: wait here until shutdown is requested
