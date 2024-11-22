import asyncio
import contextlib
import datetime
import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Final

from common_library.errors_classes import OsparcErrorMixin
from tenacity import TryAgain
from tenacity.asyncio import AsyncRetrying
from tenacity.stop import stop_after_attempt
from tenacity.wait import wait_fixed

from .decorators import async_delayed
from .logging_utils import log_catch, log_context

_logger = logging.getLogger(__name__)


_DEFAULT_STOP_TIMEOUT_S: Final[int] = 5
_MAX_TASK_CANCELLATION_ATTEMPTS: Final[int] = 3


class PeriodicTaskCancellationError(OsparcErrorMixin, Exception):
    msg_template: str = "Could not cancel task '{task_name}'"


class SleepUsingAsyncioEvent:
    """Sleep strategy that waits on an event to be set."""

    def __init__(self, event: "asyncio.Event") -> None:
        self.event = event

    async def __call__(self, timeout: float | None) -> None:
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(self.event.wait(), timeout=timeout)
            self.event.clear()


async def _periodic_scheduled_task(
    task: Callable[..., Awaitable[None]],
    *,
    interval: datetime.timedelta,
    task_name: str,
    early_wake_up_event: asyncio.Event | None,
    **task_kwargs,
) -> None:
    # NOTE: This retries forever unless cancelled
    nap = (
        asyncio.sleep
        if early_wake_up_event is None
        else SleepUsingAsyncioEvent(early_wake_up_event)
    )
    async for attempt in AsyncRetrying(
        sleep=nap,
        wait=wait_fixed(interval.total_seconds()),
    ):
        with attempt:
            with log_context(
                _logger,
                logging.DEBUG,
                msg=f"iteration {attempt.retry_state.attempt_number} of '{task_name}'",
            ), log_catch(_logger):
                await task(**task_kwargs)

            raise TryAgain


def start_periodic_task(
    task: Callable[..., Awaitable[None]],
    *,
    interval: datetime.timedelta,
    task_name: str,
    wait_before_running: datetime.timedelta = datetime.timedelta(0),
    early_wake_up_event: asyncio.Event | None = None,
    **kwargs,
) -> asyncio.Task:
    with log_context(
        _logger, logging.DEBUG, msg=f"create periodic background task '{task_name}'"
    ):
        delayed_periodic_scheduled_task = async_delayed(wait_before_running)(
            _periodic_scheduled_task
        )
        return asyncio.create_task(
            delayed_periodic_scheduled_task(
                task,
                interval=interval,
                task_name=task_name,
                early_wake_up_event=early_wake_up_event,
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
                task_name = task.get_name()
                _logger.info(
                    "tried to cancel '%s' but timed-out! %s", task_name, pending
                )
                raise PeriodicTaskCancellationError(task_name=task_name)


async def stop_periodic_task(
    asyncio_task: asyncio.Task, *, timeout: float | None = None
) -> None:
    with log_context(
        _logger,
        logging.DEBUG,
        msg=f"cancel periodic background task '{asyncio_task.get_name()}'",
    ):
        await cancel_task(asyncio_task, timeout=timeout)


@contextlib.asynccontextmanager
async def periodic_task(
    task: Callable[..., Awaitable[None]],
    *,
    interval: datetime.timedelta,
    task_name: str,
    stop_timeout: float = _DEFAULT_STOP_TIMEOUT_S,
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
            await asyncio.shield(stop_periodic_task(asyncio_task, timeout=stop_timeout))
