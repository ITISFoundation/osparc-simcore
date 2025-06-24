import asyncio
import contextlib
import datetime
import functools
import logging
from collections.abc import AsyncIterator, Awaitable, Callable, Coroutine
from typing import Any, Final, ParamSpec, TypeVar

from common_library.async_tools import cancel_and_wait, delayed_start
from tenacity import TryAgain, before_sleep_log, retry, retry_if_exception_type
from tenacity.wait import wait_fixed

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
    """Calls the function periodically with a given interval.

    Arguments:
        interval -- the interval between calls

    Keyword Arguments:
        raise_on_error -- If False the function will be retried indefinitely unless cancelled.
                          If True the function will be retried indefinitely unless cancelled
                          or an exception is raised. (default: {False})
        early_wake_up_event -- allows to awaken the function before the interval has passed. (default: {None})

    Returns:
        coroutine that will be called periodically (runs forever)
    """

    def _decorator(
        func: Callable[P, Coroutine[Any, Any, None]],
    ) -> Callable[P, Coroutine[Any, Any, None]]:
        class _InternalTryAgain(TryAgain):
            # Local exception to prevent reacting to similarTryAgain exceptions raised by the wrapped func
            # e.g. when this decorators is used twice on the same function
            ...

        nap = (
            asyncio.sleep
            if early_wake_up_event is None
            else SleepUsingAsyncioEvent(early_wake_up_event)
        )

        @retry(
            sleep=nap,
            wait=wait_fixed(interval.total_seconds()),
            reraise=True,
            retry=(
                retry_if_exception_type(_InternalTryAgain)
                if raise_on_error
                else retry_if_exception_type()
            ),
            before_sleep=before_sleep_log(_logger, logging.DEBUG),
        )
        @functools.wraps(func)
        async def _wrapper(*args: P.args, **kwargs: P.kwargs) -> None:
            with log_catch(_logger, reraise=True):
                await func(*args, **kwargs)
            raise _InternalTryAgain

        return _wrapper

    return _decorator


def create_periodic_task(
    task: Callable[..., Awaitable[None]],
    *,
    interval: datetime.timedelta,
    task_name: str,
    raise_on_error: bool = False,
    wait_before_running: datetime.timedelta = datetime.timedelta(0),
    early_wake_up_event: asyncio.Event | None = None,
    **kwargs,
) -> asyncio.Task:
    @delayed_start(wait_before_running)
    @periodic(
        interval=interval,
        raise_on_error=raise_on_error,
        early_wake_up_event=early_wake_up_event,
    )
    async def _() -> None:
        await task(**kwargs)

    with log_context(
        _logger, logging.DEBUG, msg=f"create periodic background task '{task_name}'"
    ):
        return asyncio.create_task(_(), name=task_name)


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
        asyncio_task = create_periodic_task(
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
            await asyncio.shield(cancel_and_wait(asyncio_task, max_delay=stop_timeout))
