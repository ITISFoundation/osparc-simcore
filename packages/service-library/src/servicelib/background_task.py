import asyncio
import contextlib
import datetime
import functools
import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any, Coroutine, Final, ParamSpec, TypeVar

from tenacity import TryAgain, before_sleep_log, retry, retry_if_exception_type
from tenacity.asyncio import AsyncRetrying
from tenacity.wait import wait_fixed

from .async_utils import retried_cancel_task, with_delay
from .logging_utils import log_catch, log_context

_logger = logging.getLogger(__name__)


_DEFAULT_STOP_TIMEOUT_S: Final[int] = 5


class SleepUsingAsyncioEvent:
    """Sleep strategy that waits on an event to be set or sleeps."""

    def __init__(self, event: "asyncio.Event") -> None:
        self.event = event

    async def __call__(self, delay: float | None) -> None:
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(self.event.wait(), timeout=delay)
            self.event.clear()


P = ParamSpec("P")
R = TypeVar("R")


def periodic(
    *,
    interval: datetime.timedelta,
    raise_on_error: bool = False,
    early_wake_up_event: asyncio.Event | None = None,
) -> Callable[
    [Callable[P, Coroutine[Any, Any, None]]], Callable[P, Coroutine[Any, Any, None]]
]:
    def _decorator(
        func: Callable[P, Coroutine[Any, Any, None]],
    ) -> Callable[P, Coroutine[Any, Any, None]]:
        nap = (
            asyncio.sleep
            if early_wake_up_event is None
            else SleepUsingAsyncioEvent(early_wake_up_event)
        )

        @retry(
            sleep=nap,
            wait=wait_fixed(interval.total_seconds()),
            reraise=True,
            retry=retry_if_exception_type(TryAgain)
            if raise_on_error
            else retry_if_exception_type(),
            before_sleep=before_sleep_log(_logger, logging.DEBUG),
        )
        @functools.wraps(func)
        async def _wrapper(*args: P.args, **kwargs: P.kwargs) -> None:
            await func(*args, **kwargs)
            raise TryAgain

        return _wrapper

    return _decorator


async def _periodic_scheduled_task(
    task: Callable[..., Awaitable[None]],
    *,
    interval: datetime.timedelta,
    task_name: str,
    raise_on_error: bool,
    early_wake_up_event: asyncio.Event | None,
    **task_kwargs,
) -> None:
    """periodically runs task with a given interval.
    If raise_on_error is False, the task will be retried indefinitely unless cancelled.
    If raise_on_error is True, the task will be retried indefinitely unless cancelled or an exception is raised.
    If early_wake_up_event is set, the task might be woken up earlier than interval when the event is set.

    Raises:
        task exception if raise_on_error is True
    """
    nap = (
        asyncio.sleep
        if early_wake_up_event is None
        else SleepUsingAsyncioEvent(early_wake_up_event)
    )
    async for attempt in AsyncRetrying(
        sleep=nap,
        wait=wait_fixed(interval.total_seconds()),
        reraise=True,
        retry=retry_if_exception_type(TryAgain)
        if raise_on_error
        else retry_if_exception_type(),
    ):
        with attempt:
            with (
                log_context(
                    _logger,
                    logging.DEBUG,
                    msg=f"iteration {attempt.retry_state.attempt_number} of '{task_name}'",
                ),
                log_catch(_logger),
            ):
                await task(**task_kwargs)

            raise TryAgain


def start_periodic_task(
    task: Callable[..., Awaitable[None]],
    *,
    interval: datetime.timedelta,
    task_name: str,
    raise_on_error: bool = False,
    wait_before_running: datetime.timedelta = datetime.timedelta(0),
    early_wake_up_event: asyncio.Event | None = None,
    **kwargs,
) -> asyncio.Task:
    with log_context(
        _logger, logging.DEBUG, msg=f"create periodic background task '{task_name}'"
    ):
        delayed_periodic_scheduled_task = with_delay(wait_before_running)(
            _periodic_scheduled_task
        )
        return asyncio.create_task(
            delayed_periodic_scheduled_task(
                task,
                interval=interval,
                task_name=task_name,
                raise_on_error=raise_on_error,
                early_wake_up_event=early_wake_up_event,
                **kwargs,
            ),
            name=task_name,
        )


async def stop_periodic_task(
    asyncio_task: asyncio.Task, *, timeout: float | None = None
) -> None:
    with log_context(
        _logger,
        logging.DEBUG,
        msg=f"cancel periodic background task '{asyncio_task.get_name()}'",
    ):
        await retried_cancel_task(asyncio_task, timeout=timeout)


@contextlib.asynccontextmanager
async def periodic_task(
    task: Callable[..., Awaitable[None]],
    *,
    interval: datetime.timedelta,
    task_name: str,
    stop_timeout: float = _DEFAULT_STOP_TIMEOUT_S,
    raise_on_error: bool = False,
    **kwargs,
) -> AsyncIterator[asyncio.Task]:
    asyncio_task: asyncio.Task | None = None
    try:
        asyncio_task = start_periodic_task(
            task,
            interval=interval,
            task_name=task_name,
            raise_on_error=raise_on_error,
            **kwargs,
        )
        yield asyncio_task
    finally:
        if asyncio_task is not None:
            # NOTE: this stopping is shielded to prevent the cancellation to propagate
            # into the stopping procedure
            await asyncio.shield(stop_periodic_task(asyncio_task, timeout=stop_timeout))
