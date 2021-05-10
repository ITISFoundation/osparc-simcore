"""The scheduler shall be run as a background task.
Based on oSparc pipelines, it monitors when to start the next celery task(s), either one at a time or as a group of tasks.
"""
import asyncio
import logging
from asyncio import CancelledError

from fastapi import FastAPI

logger = logging.getLogger(__name__)


async def scheduler_task(app: FastAPI) -> None:
    while True:
        try:
            logger.info("Scheduler checking running tasks")
            await asyncio.sleep(5)
        except CancelledError:
            logger.info("Scheduler background task cancelled")
            return
        except Exception:  # pylint: disable=broad-except
            logger.exception(
                "Unexpected error in scheduler task, restarting scheduler..."
            )
            # wait a bit before restarting the task
            await asyncio.sleep(5)
