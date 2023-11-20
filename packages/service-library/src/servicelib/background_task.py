import asyncio
import contextlib
import datetime
import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Final, cast

from pydantic.errors import PydanticErrorMixin
from servicelib.logging_utils import log_catch, log_context
from tenacity import TryAgain
from tenacity._asyncio import AsyncRetrying
from tenacity.stop import stop_after_attempt
from tenacity.wait import wait_fixed

logger = logging.getLogger(__name__)


_DEFAULT_STOP_TIMEOUT_S: Final[int] = 5
_MAX_TASK_CANCELLATION_ATTEMPTS: Final[int] = 3


class PeriodicTaskCancellationError(PydanticErrorMixin, Exception):
    msg_template: str = "Could not cancel task '{task_name}'"


class ContinueCondition:
    def __init__(self) -> None:
        self._can_continue: bool = True

    def stop(self):
        self._can_continue = False

    @property
    def can_continue(self) -> bool:
        return self._can_continue


class _ExtendedTask(asyncio.Task):
    def __init__(self, coro, *, loop=None, name=None):
        super().__init__(coro=coro, loop=loop, name=name)
        self.continue_condition: ContinueCondition | None = None


async def _periodic_scheduled_task(
    task: Callable[..., Awaitable[None]],
    *,
    interval: datetime.timedelta,
    continue_condition: ContinueCondition,
    task_name: str,
    **task_kwargs,
) -> None:
    # NOTE: This retries forever unless cancelled or stopped
    async for attempt in AsyncRetrying(wait=wait_fixed(interval.total_seconds())):
        with attempt:
            if not continue_condition.can_continue:
                logger.debug("'%s' finished periodic actions", task_name)
                return
            with log_context(
                logger,
                logging.DEBUG,
                msg=f"iteration {attempt.retry_state.attempt_number} of '{task_name}'",
            ), log_catch(logger):
                await task(**task_kwargs)

            raise TryAgain


def start_periodic_task(
    task: Callable[..., Awaitable[None]],
    *,
    interval: datetime.timedelta,
    task_name: str,
    **kwargs,
) -> asyncio.Task:
    with log_context(
        logger, logging.DEBUG, msg=f"create periodic background task '{task_name}'"
    ):
        continue_condition = ContinueCondition()
        new_periodic_task: asyncio.Task = asyncio.create_task(
            _periodic_scheduled_task(
                task,
                interval=interval,
                continue_condition=continue_condition,
                task_name=task_name,
                **kwargs,
            ),
            name=task_name,
        )
        # NOTE: adds an additional property to the task object
        # which will be used when stopping the periodic task
        new_periodic_task = cast(_ExtendedTask, new_periodic_task)
        new_periodic_task.continue_condition = continue_condition
        return new_periodic_task


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
                logger.info(
                    "tried to cancel '%s' but timed-out! %s", task_name, pending
                )
                raise PeriodicTaskCancellationError(task_name=task_name)


async def stop_periodic_task(
    asyncio_task: asyncio.Task, *, timeout: float | None = None
) -> None:
    with log_context(
        logger,
        logging.DEBUG,
        msg=f"stop periodic background task '{asyncio_task.get_name()}'",
    ):
        asyncio_task = cast(_ExtendedTask, asyncio_task)
        continue_condition: ContinueCondition | None = asyncio_task.continue_condition
        if continue_condition:
            continue_condition.stop()

        _, pending = await asyncio.wait((asyncio_task,), timeout=timeout)
        if pending:
            with log_context(
                logger,
                logging.WARNING,
                msg=f"could not gracefully stop task '{asyncio_task.get_name()}', cancelling it",
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
