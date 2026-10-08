import asyncio
import contextlib
import datetime
import functools
import logging
from collections.abc import AsyncGenerator, Awaitable, Callable, Coroutine
from typing import Annotated, Any, Final, ParamSpec

from annotated_types import doc
from common_library.async_tools import cancel_wait_task, delayed_start
from tenacity import TryAgain, before_sleep_log, retry, retry_if_exception_type
from tenacity.wait import wait_fixed

from .logging_utils import log_catch, log_context
from .utils import get_callable_namespaced_name

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


def periodic(
    *,
    interval: Annotated[datetime.timedelta, doc("the interval between calls")],
    raise_on_error: Annotated[
        bool,
        doc(
            "if True, an exception raised by the wrapped function stops the loop; "
            "if False (default) it is retried indefinitely until cancelled"
        ),
    ] = False,
    early_wake_up_event: Annotated[
        asyncio.Event | None, doc("when set, wakes up the function before ``interval`` elapses")
    ] = None,
) -> Annotated[
    Callable[[Callable[P, Coroutine[Any, Any, None]]], Callable[P, Coroutine[Any, Any, None]]],
    doc("decorator that runs the wrapped coroutine function forever"),
]:
    """Calls the wrapped function periodically, or earlier when ``early_wake_up_event`` is set."""

    def _decorator(
        async_fun: Callable[P, Coroutine[Any, Any, None]],
    ) -> Callable[P, Coroutine[Any, Any, None]]:
        class _InternalTryAgain(TryAgain):
            # Local exception to prevent reacting to similarTryAgain exceptions raised by the wrapped func
            # e.g. when this decorators is used twice on the same function
            ...

        nap = asyncio.sleep if early_wake_up_event is None else SleepUsingAsyncioEvent(early_wake_up_event)

        @retry(
            sleep=nap,
            wait=wait_fixed(interval.total_seconds()),
            reraise=True,
            retry=(retry_if_exception_type(_InternalTryAgain) if raise_on_error else retry_if_exception_type()),
            before_sleep=before_sleep_log(_logger, logging.DEBUG),
        )
        @functools.wraps(async_fun)
        async def _wrapper(*args: P.args, **kwargs: P.kwargs) -> None:
            with log_catch(_logger, reraise=True):
                await async_fun(*args, **kwargs)
            raise _InternalTryAgain

        return _wrapper

    return _decorator


def create_periodic_task(
    task: Annotated[Callable[..., Awaitable[None]], doc("the coroutine function to run on every iteration")],
    *,
    interval: Annotated[datetime.timedelta, doc("the interval between two consecutive runs")],
    task_name: Annotated[
        str | None,
        doc(
            "name given to the underlying asyncio task; if omitted, a namespaced name is "
            "derived from the callable (see :func:`servicelib.utils.get_callable_namespaced_name`)"
        ),
    ] = None,
    raise_on_error: Annotated[
        bool,
        doc(
            "if True, an exception raised by ``task`` stops the periodic loop; "
            "if False (default) the task is retried indefinitely until cancelled"
        ),
    ] = False,
    wait_before_running: Annotated[
        datetime.timedelta, doc("delay before the first run (default: no delay)")
    ] = datetime.timedelta(0),
    early_wake_up_event: Annotated[
        asyncio.Event | None, doc("when set, wakes up the task before ``interval`` elapses")
    ] = None,
    **kwargs: Annotated[Any, doc("forwarded to ``task`` on every call")],
) -> Annotated[asyncio.Task[None], doc("the running task, owned by the caller")]:
    """Creates an :class:`asyncio.Task` that runs ``task`` periodically until cancelled.

    The caller owns the returned task and is responsible for cancelling it (e.g. via
    ``cancel_wait_task``); prefer :func:`periodic_task` when a managed lifetime is enough.
    """
    resolved_task_name = task_name or get_callable_namespaced_name(task)

    @delayed_start(wait_before_running)
    @periodic(
        interval=interval,
        raise_on_error=raise_on_error,
        early_wake_up_event=early_wake_up_event,
    )
    async def _() -> None:
        await task(**kwargs)

    with log_context(_logger, logging.DEBUG, msg=f"create periodic background task '{resolved_task_name}'"):
        return asyncio.create_task(_(), name=resolved_task_name)


@contextlib.asynccontextmanager
async def periodic_task(
    task: Annotated[Callable[..., Awaitable[None]], doc("the coroutine function to run on every iteration")],
    *,
    interval: Annotated[datetime.timedelta, doc("the interval between two consecutive runs")],
    task_name: Annotated[
        str | None,
        doc(
            "name given to the underlying asyncio task; if omitted, a namespaced name is "
            "derived from the callable (see :func:`servicelib.utils.get_callable_namespaced_name`)"
        ),
    ] = None,
    stop_timeout: Annotated[float, doc("maximum time to wait for the task to stop on exit")] = _DEFAULT_STOP_TIMEOUT_S,
    raise_on_error: Annotated[
        bool,
        doc(
            "if True, an exception raised by ``task`` stops the periodic loop; "
            "if False (default) the task is retried indefinitely until cancelled"
        ),
    ] = False,
    early_wake_up_event: Annotated[
        asyncio.Event | None, doc("when set, wakes up the task before ``interval`` elapses")
    ] = None,
    **kwargs: Annotated[Any, doc("forwarded to ``task`` on every call")],
) -> AsyncGenerator[asyncio.Task[None]]:
    """Async context manager that runs ``task`` periodically and cancels it on exit.

    Wraps :func:`create_periodic_task` and guarantees the task is stopped when the
    context is left, even if an exception occurs. Yields the underlying asyncio task.
    """
    asyncio_task: asyncio.Task[None] | None = None
    try:
        asyncio_task = create_periodic_task(
            task,
            interval=interval,
            task_name=task_name,
            raise_on_error=raise_on_error,
            early_wake_up_event=early_wake_up_event,
            **kwargs,
        )
        yield asyncio_task
    finally:
        if asyncio_task is not None:
            await cancel_wait_task(asyncio_task, max_delay=stop_timeout)
