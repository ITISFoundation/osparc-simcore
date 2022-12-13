import asyncio
import contextlib
import datetime
import logging
from typing import AsyncIterator, Awaitable, Callable, Optional

from servicelib.logging_utils import log_catch, log_context
from tenacity import TryAgain
from tenacity._asyncio import AsyncRetrying
from tenacity.wait import wait_fixed

logger = logging.getLogger(__name__)


async def _periodic_scheduled_task(
    task: Callable[..., Awaitable[None]],
    *,
    interval: datetime.timedelta,
    task_name: str,
    **task_kwargs,
):
    # NOTE: This retries forever unless cancelled
    async for attempt in AsyncRetrying(wait=wait_fixed(interval.total_seconds())):
        with attempt:
            with log_context(
                logger,
                logging.DEBUG,
                msg=f"Run {task_name}, {attempt.retry_state.attempt_number=}",
            ), log_catch(logger):
                await task(**task_kwargs)

            raise TryAgain()


async def start_periodic_task(
    task: Callable[..., Awaitable[None]],
    *,
    interval: datetime.timedelta,
    task_name: str,
    **kwargs,
) -> asyncio.Task:
    with log_context(
        logger, logging.INFO, msg=f"create periodic background task '{task_name}'"
    ):
        return asyncio.create_task(
            _periodic_scheduled_task(
                task,
                interval=interval,
                task_name=task_name,
                **kwargs,
            ),
            name=task_name,
        )


async def stop_periodic_task(
    asyncio_task: asyncio.Task, *, timeout: Optional[float] = None
) -> None:
    with log_context(
        logger,
        logging.INFO,
        msg=f"cancel periodic background task '{asyncio_task.get_name()}'",
    ), contextlib.suppress(asyncio.CancelledError):
        asyncio_task.cancel()
        with log_catch(logger, reraise=False):
            await asyncio.wait((asyncio_task,), timeout=timeout)


@contextlib.asynccontextmanager
async def periodic_task(
    task: Callable[..., Awaitable[None]],
    *,
    interval: datetime.timedelta,
    task_name: str,
    **kwargs,
) -> AsyncIterator[None]:
    asyncio_task = None
    try:
        asyncio_task = await start_periodic_task(
            task, interval=interval, task_name=task_name, **kwargs
        )
        yield
    finally:
        if asyncio_task is not None:
            await stop_periodic_task(asyncio_task)
