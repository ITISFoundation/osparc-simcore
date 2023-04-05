import asyncio
import contextlib
import datetime
import logging
from contextlib import suppress
from typing import AsyncIterator, Awaitable, Callable, Final

from servicelib.logging_utils import log_catch, log_context
from tenacity import TryAgain
from tenacity._asyncio import AsyncRetrying
from tenacity.wait import wait_fixed

logger = logging.getLogger(__name__)


_DEFAULT_STOP_TIMEOUT_S: Final[int] = 5


async def _periodic_scheduled_task(
    task: Callable[..., Awaitable[None]],
    *,
    interval: datetime.timedelta,
    task_name: str,
    **task_kwargs,
) -> None:
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


def start_periodic_task(
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


async def _await_task(task: asyncio.Task) -> None:
    await task


async def stop_periodic_task(
    asyncio_task: asyncio.Task, *, timeout: float | None = None
) -> None:
    with log_context(
        logger,
        logging.INFO,
        msg=f"cancel periodic background task '{asyncio_task.get_name()}'",
    ):
        asyncio_task.cancel()
        with suppress(asyncio.CancelledError):
            try:
                await asyncio.wait_for(_await_task(asyncio_task), timeout=timeout)
            except asyncio.TimeoutError:
                logger.warning(
                    "periodic background task '%s' did not cancel properly and timed-out!",
                    f"{asyncio_task.get_name()}",
                )


@contextlib.asynccontextmanager
async def periodic_task(
    task: Callable[..., Awaitable[None]],
    *,
    interval: datetime.timedelta,
    task_name: str,
    **kwargs,
) -> AsyncIterator[asyncio.Task]:
    asyncio_task: asyncio.Task | None = None
    try:
        asyncio_task = start_periodic_task(
            task, interval=interval, task_name=task_name, **kwargs
        )
        yield asyncio_task
    finally:
        if asyncio_task is not None:
            # NOTE: this stopping is shielded to prevent the cancellation to propagate
            # into the stopping procedure
            await asyncio.shield(
                stop_periodic_task(asyncio_task, timeout=_DEFAULT_STOP_TIMEOUT_S)
            )
