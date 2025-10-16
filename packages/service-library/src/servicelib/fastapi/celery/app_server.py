import datetime
import logging
import threading
from typing import Final

from asgi_lifespan import LifespanManager
from fastapi import FastAPI

from ...celery.app_server import BaseAppServer
from ...celery.task_manager import TaskManager

_STARTUP_TIMEOUT: Final[float] = datetime.timedelta(minutes=5).total_seconds()
_SHUTDOWN_TIMEOUT: Final[float] = datetime.timedelta(seconds=10).total_seconds()

_logger = logging.getLogger(__name__)


class FastAPIAppServer(BaseAppServer[FastAPI]):
    @property
    def task_manager(self) -> TaskManager:
        task_manager = self.app.state.task_manager
        assert task_manager, "Task manager is not initialized"  # nosec
        assert isinstance(task_manager, TaskManager)
        return task_manager

    async def run_until_shutdown(
        self, startup_completed_event: threading.Event
    ) -> None:
        async with LifespanManager(
            self.app,
            startup_timeout=_STARTUP_TIMEOUT,
            shutdown_timeout=_SHUTDOWN_TIMEOUT,
        ):
            _logger.info("FastAPI initialized: %s", self.app)
            startup_completed_event.set()
            await self.shutdown_event.wait()  # NOTE: wait here until shutdown is requested
            _logger.info("FastAPI shutdown completed: %s", self.app)
