import asyncio
import datetime
import functools
import logging
import sys
from collections.abc import AsyncIterator, Awaitable, Callable, Coroutine
from concurrent.futures import Executor
from functools import wraps
from inspect import isawaitable
from typing import Any, ParamSpec, TypeVar, overload

from .logging.logging_errors import create_troubleshooting_log_kwargs

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
            return await loop.run_in_executor(executor, functools.partial(func, *args, **kwargs))

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


async def cancel_wait_task(task: asyncio.Task, *, max_delay: float | None = None) -> None:
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

    # NOTE: if this function is cancelled, all the sync methods will still be called
    # before propagating the CancelledError, therefore the task will still be properly cancelled

    if task.done():
        # nothing to do here
        return

    # mark for cancellation
    current_task = asyncio.current_task()
    assert current_task  # nosec
    cancelled = task.cancel(
        f"manually cancelling and waiting for task: {task.get_name()}, {current_task.cancelling()=}"
    )
    _logger.debug("task %s marked for cancellation: %s", task.get_name(), cancelled)
    try:
        _logger.debug(
            "Starting cancellation of task: %s, current_task is cancelling: %d",
            task.get_name(),
            current_task.cancelling(),
        )
        # NOTE: using wait here so that the cancellation error on task is not propagated to us
        done, pending = await asyncio.wait((task,), timeout=max_delay)
        if pending:
            raise TimeoutError  # noqa: TRY301
        assert task in done  # nosec
        _logger.debug(
            "Finished cancellation of task: %s, current_task is cancelling: %d",
            task.get_name(),
            current_task.cancelling(),
        )
        if not task.cancelled() and (task_exception := task.exception()):
            assert task_exception  # nosec
            _logger.debug(
                "Task %s raised exception after cancellation: %s",
                task.get_name(),
                task_exception,
            )

            raise task_exception
    except TimeoutError as exc:
        _logger.exception(
            **create_troubleshooting_log_kwargs(
                f"Timeout while cancelling task {task.get_name()} after {max_delay} seconds",
                error=exc,
                error_context={
                    "task_name": task.get_name(),
                    "max_delay": max_delay,
                    "current_task_cancelling": current_task.cancelling(),
                },
            )
        )
        raise
    except asyncio.CancelledError as exc:
        _logger.debug(
            "Cancellation of task %s was itself cancelled: %s, current_task cancelling=%d",
            task.get_name(),
            exc,
            current_task.cancelling(),
        )
        raise
    finally:
        if not task.done():
            current_exception = sys.exception()
            _logger.error(
                **create_troubleshooting_log_kwargs(
                    f"Failed to cancel task {task.get_name()}",
                    error=(current_exception if current_exception else Exception("Unknown")),
                    error_context={
                        "task_name": task.get_name(),
                        "max_delay": max_delay,
                        "current_task_cancelling": current_task.cancelling(),
                    },
                    tip="Consider increasing max_delay or fixing the task to handle cancellations properly",
                )
            )
        else:
            _logger.debug(
                "Task %s cancelled, current_task cancelling=%d",
                task.get_name(),
                current_task.cancelling(),
            )


def delayed_start(
    delay: datetime.timedelta,
) -> Callable[[Callable[P, Coroutine[Any, Any, R]]], Callable[P, Coroutine[Any, Any, R]]]:
    def _decorator(
        func: Callable[P, Coroutine[Any, Any, R]],
    ) -> Callable[P, Coroutine[Any, Any, R]]:
        @wraps(func)
        async def _wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            await asyncio.sleep(delay.total_seconds())
            return await func(*args, **kwargs)

        return _wrapper

    return _decorator


async def iter_with_timeout[T](
    it: AsyncIterator[T],
    *,
    per_iteration_timeout: datetime.timedelta,
) -> AsyncIterator[T]:
    """Yields items from an async iterator with a timeout for each iteration."""
    try:
        while True:
            try:
                item = await asyncio.wait_for(anext(it), per_iteration_timeout.total_seconds())
            except StopAsyncIteration:
                break
            else:
                yield item
    finally:
        aclose = getattr(it, "aclose", None)  # NOTE: with async iterators, aclose might not be present
        if aclose is not None:
            await aclose()
