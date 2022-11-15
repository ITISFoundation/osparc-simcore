import asyncio
import contextlib
import datetime
import logging
from typing import Awaitable, Callable

from servicelib.logging_utils import log_context

logger = logging.getLogger(__name__)


async def _repeated_scheduled_task(
    task: Callable[..., Awaitable[None]],
    *,
    interval: datetime.timedelta,
    task_name: str,
    **kwargs,
):
    while await asyncio.sleep(interval.total_seconds(), result=True):
        try:
            with log_context(logger, logging.DEBUG, msg=f"Run {task_name}"):
                await task(**kwargs)
        except asyncio.CancelledError:
            logger.info("%s cancelled", task_name)
            raise
        except Exception:  # pylint: disable=broad-except
            logger.exception("Unexpected error in %s, restarting...", task_name)


async def start_background_task(
    task: Callable[..., Awaitable[None]],
    *,
    interval: datetime.timedelta,
    task_name: str,
    **kwargs,
) -> asyncio.Task:
    with log_context(logger, logging.INFO, msg=f"create {task_name}"):
        return asyncio.create_task(
            _repeated_scheduled_task(
                task,
                interval=interval,
                task_name=task_name,
                **kwargs,
            ),
            name=task_name,
        )


async def stop_background_task(asyncio_task: asyncio.Task) -> None:
    with log_context(
        logger, logging.INFO, msg=f"remove {asyncio_task.get_name()}"
    ), contextlib.suppress(asyncio.CancelledError):
        asyncio_task.cancel()
        await asyncio_task
