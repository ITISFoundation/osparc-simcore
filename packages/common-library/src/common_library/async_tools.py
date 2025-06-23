import asyncio
import functools
import logging
from collections.abc import Awaitable, Callable
from concurrent.futures import Executor
from inspect import isawaitable
from typing import ParamSpec, TypeVar, overload

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


async def cancel_and_wait(task: asyncio.Task) -> None:
    """Cancels the given task and waits for it to finish.

    Accounts for the case where the tasks's owner function is being cancelled
    """
    task.cancel()
    try:
        # NOTE shield ensures that cancellation of the caller function won’t stop you
        # from observing the cancellation/finalization of task.
        await asyncio.shield(task)
    except asyncio.CancelledError:
        if not task.cancelled():
            # task owner function is being cancelled -> propagate cancellation
            raise
        # else: task cancellation is complete, we can safely ignore it
        _logger.debug(
            "Task %s cancellation is complete",
            task.get_name(),
        )
