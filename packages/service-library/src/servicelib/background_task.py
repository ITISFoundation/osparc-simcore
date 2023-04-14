import asyncio
import contextlib
import datetime
import logging
from typing import AsyncIterator, Awaitable, Callable, Final

from servicelib.logging_utils import log_catch, log_context
from tenacity import TryAgain
from tenacity._asyncio import AsyncRetrying
from tenacity.stop import stop_after_attempt
from tenacity.wait import wait_fixed

logger = logging.getLogger(__name__)


_DEFAULT_STOP_TIMEOUT_S: Final[int] = 5
_MAX_TASK_CANCELLATION_ATTEMPTS: Final[int] = 3


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
                msg=f"iteration {attempt.retry_state.attempt_number} of '{task_name}'",
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


async def cancel_task(
    task: asyncio.Task,
    *,
    timeout: float | None,
    cancellation_attempts: int = _MAX_TASK_CANCELLATION_ATTEMPTS,
) -> None:
    """Reliable task cancellation. Some libraries will just hang without
    cancelling the task. It is important to retry the operation to provide
    a timeout in that situation to avoid forever pending tasks.

    :param task: task to be canceled
    :param timeout: total duration (in seconds) to wait before giving
        up the cancellation. If None it waits forever.
    :raises TryAgain: raised if cannot cancel the task.
    """
    async for attempt in AsyncRetrying(
        stop=stop_after_attempt(cancellation_attempts), reraise=True
    ):
        with attempt:
            task.cancel()
            _, pending = await asyncio.wait((task,), timeout=timeout)
            if pending:
                logger.info(
                    "tried to cancel '%s' but timed-out! %s", task.get_name(), pending
                )
                raise TryAgain()


async def stop_periodic_task(
    asyncio_task: asyncio.Task, *, timeout: float | None = None
) -> None:
    with log_context(
        logger,
        logging.INFO,
        msg=f"cancel periodic background task '{asyncio_task.get_name()}'",
    ):
        await cancel_task(asyncio_task, timeout=timeout)


@contextlib.asynccontextmanager
async def periodic_task(
    task: Callable[..., Awaitable[None]],
    *,
    interval: datetime.timedelta,
    task_name: str,
    stop_timeout: float | None = None,
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
            await asyncio.shield(
                stop_periodic_task(
                    asyncio_task, timeout=stop_timeout or _DEFAULT_STOP_TIMEOUT_S
                )
            )
