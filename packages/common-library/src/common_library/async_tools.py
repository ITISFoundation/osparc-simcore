import asyncio
import datetime
import functools
import logging
from collections.abc import Awaitable, Callable, Coroutine
from concurrent.futures import Executor
from functools import wraps
from inspect import isawaitable
from typing import Any, ParamSpec, TypeVar, overload

_logger = logging.getLogger(__name__)

R = TypeVar("R")
P = ParamSpec("P")


def make_async(
    executor: Executor | None = None,
) -> Callable[[Callable[P, R]], Callable[P, Awaitable[R]]]:
    def decorator(func: Callable[P, R]) -> Callable[P, Awaitable[R]]:
        @functools.wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(
                executor, functools.partial(func, *args, **kwargs)
            )

        return wrapper

    return decorator


_AwaitableResult = TypeVar("_AwaitableResult")


@overload
async def maybe_await(obj: Awaitable[_AwaitableResult]) -> _AwaitableResult: ...


@overload
async def maybe_await(obj: _AwaitableResult) -> _AwaitableResult: ...


async def maybe_await(
    obj: Awaitable[_AwaitableResult] | _AwaitableResult,
) -> _AwaitableResult:
    """Helper function to handle both async and sync database results.

    This function allows code to work with both aiopg (async) and asyncpg (sync) result methods
    by automatically detecting and handling both cases.

    Args:
        obj: Either an awaitable coroutine or direct result value

    Returns:
        The result value, after awaiting if necessary

    Example:
        ```python
        result = await conn.execute(query)
        # Works with both aiopg and asyncpg
        row = await maybe_await(result.fetchone())
        ```
    """
    if isawaitable(obj):
        assert isawaitable(obj)  # nosec
        return await obj
    assert not isawaitable(obj)  # nosec
    return obj


async def cancel_wait_task(
    task: asyncio.Task, *, max_delay: float | None = None
) -> None:
    """Cancels the given task and waits for it to complete

    Arguments:
        task -- task to be canceled


    Keyword Arguments:
        max_delay -- duration (in seconds) to wait before giving
        up the cancellation. This timeout should be an upper bound to the
        time needed for the task to cleanup after being canceled and
        avoids that the cancellation takes forever. If None the timeout is not
        set. (default: {None})

    Raises:
        TimeoutError: raised if cannot cancel the task.
        CancelledError: raised ONLY if owner is being cancelled.
    """

    cancelling = task.cancel()
    if not cancelling:
        return  # task was alredy cancelled

    assert task.cancelling()  # nosec
    assert not task.cancelled()  # nosec

    try:

        await asyncio.shield(
            # NOTE shield ensures that cancellation of the caller function won't stop you
            # from observing the cancellation/finalization of task.
            asyncio.wait_for(task, timeout=max_delay)
        )

    except asyncio.CancelledError:
        if not task.cancelled():
            # task owner function is being cancelled -> propagate cancellation
            raise

        # else: task cancellation is complete, we can safely ignore it
        _logger.debug(
            "Task %s cancellation is complete",
            task.get_name(),
        )


def delayed_start(
    delay: datetime.timedelta,
) -> Callable[
    [Callable[P, Coroutine[Any, Any, R]]], Callable[P, Coroutine[Any, Any, R]]
]:
    def _decorator(
        func: Callable[P, Coroutine[Any, Any, R]],
    ) -> Callable[P, Coroutine[Any, Any, R]]:
        @wraps(func)
        async def _wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            await asyncio.sleep(delay.total_seconds())
            return await func(*args, **kwargs)

        return _wrapper

    return _decorator
