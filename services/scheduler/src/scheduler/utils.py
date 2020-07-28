import asyncio
import logging
import traceback
from typing import Coroutine, Dict

from structlog import get_logger


class AsyncTaskWrapper:
    """Used to handle cleanup of tasks"""

    def __init__(self, worker: Coroutine, logger: logging.Logger):
        self._worker = worker
        self.logger = logger
        self.task = None

    async def worker_wrapper(self):
        should_restart = True
        try:
            self.logger.info("Starting %s", self._worker.__name__)
            await self._worker()
        except asyncio.CancelledError:
            self.logger.warning("Task was canceled. Exiting")
            should_restart = False
        except Exception:  # pylint: disable=broad-except
            self.logger.error(
                "%s\nThe above exception happened in %s",
                traceback.format_exc(),
                self._worker.__name__,
            )
        finally:
            self.logger.warning(
                "Worker '%s' exited.", self._worker.__name__,
            )

        if should_restart:
            self.start()

    def start(self):
        """starts the worker and returns self instance to be used later """
        self.task = asyncio.get_event_loop().create_task(self.worker_wrapper())
        return self

    async def force_cleanup(self):
        """Used for cleanup when shitting down the app"""
        self.task.cancel()
        await self.task


def get_tracking_log(dict_with_tracking_and_project: Dict) -> logging.Logger:
    """Bind the current operation context to a logger"""
    log = get_logger().bind(
        project_id=dict_with_tracking_and_project["project_id"],
        tracking_id=dict_with_tracking_and_project["tracking_id"],
    )
    return log
