import asyncio
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from typing import Any

import pytest
from common_library.async_tools import (
    cancel_and_shielded_wait,
    delayed_start,
    make_async,
    maybe_await,
)


@make_async()
def sync_function(x: int, y: int) -> int:
    return x + y


@make_async()
def sync_function_with_exception() -> None:
    msg = "This is an error!"
    raise ValueError(msg)


@pytest.mark.asyncio
async def test_make_async_returns_coroutine():
    result = sync_function(2, 3)
    assert asyncio.iscoroutine(result), "Function should return a coroutine"


@pytest.mark.asyncio
async def test_make_async_execution():
    result = await sync_function(2, 3)
    assert result == 5, "Function should return 5"


@pytest.mark.asyncio
async def test_make_async_exception():
    with pytest.raises(ValueError, match="This is an error!"):
        await sync_function_with_exception()


@pytest.mark.asyncio
async def test_make_async_with_executor():
    executor = ThreadPoolExecutor()

    @make_async(executor)
    def heavy_computation(x: int) -> int:
        return x * x

    result = await heavy_computation(4)
    assert result == 16, "Function should return 16"


@pytest.mark.asyncio
async def test_maybe_await_with_coroutine():
    """Test maybe_await with an async function"""

    async def async_value():
        return 42

    result = await maybe_await(async_value())
    assert result == 42


@pytest.mark.asyncio
async def test_maybe_await_with_direct_value():
    """Test maybe_await with a direct value"""
    value = 42
    result = await maybe_await(value)
    assert result == 42


@pytest.mark.asyncio
async def test_maybe_await_with_none():
    """Test maybe_await with None value"""
    result = await maybe_await(None)
    assert result is None


@pytest.mark.asyncio
async def test_maybe_await_with_result_proxy():
    """Test maybe_await with both async and sync ResultProxy implementations"""

    class AsyncResultProxy:
        """Mock async result proxy (aiopg style)"""

        async def fetchone(self) -> Any:  # pylint: disable=no-self-use
            return {"id": 1, "name": "test"}

    class SyncResultProxy:
        """Mock sync result proxy (asyncpg style)"""

        def fetchone(self) -> Any:  # pylint: disable=no-self-use
            return {"id": 2, "name": "test2"}

    async_result = await maybe_await(AsyncResultProxy().fetchone())
    assert async_result == {"id": 1, "name": "test"}

    sync_result = await maybe_await(SyncResultProxy().fetchone())
    assert sync_result == {"id": 2, "name": "test2"}


async def test_cancel_and_wait():
    state = {"started": False, "cancelled": False, "cleaned_up": False}
    SLEEP_TIME = 5  # seconds

    async def coro():
        try:
            state["started"] = True
            await asyncio.sleep(SLEEP_TIME)
        except asyncio.CancelledError:
            state["cancelled"] = True
            raise
        finally:
            state["cleaned_up"] = True

    task = asyncio.create_task(coro())
    await asyncio.sleep(0.1)  # Let coro start

    start = time.time()
    await cancel_and_shielded_wait(task)

    elapsed = time.time() - start
    assert elapsed < SLEEP_TIME, "Task should be cancelled quickly"
    assert task.done()
    assert task.cancelled()
    assert state["started"]
    assert state["cancelled"]
    assert state["cleaned_up"]


async def test_cancel_and_wait_propagates_external_cancel():
    """
    This test ensures that if the caller of cancel_and_wait is cancelled,
    the CancelledError is not swallowed.
    """

    async def coro():
        try:
            await asyncio.sleep(4)
        except asyncio.CancelledError:
            await asyncio.sleep(1)  # simulate cleanup
            raise

    inner_task = asyncio.create_task(coro())

    async def outer_coro():
        try:
            await cancel_and_shielded_wait(inner_task)
        except asyncio.CancelledError:
            assert (
                not inner_task.cancelled()
            ), "Internal Task DOES NOT RAISE CancelledError"
            raise

    # Cancel the wrapper after a short delay
    outer_task = asyncio.create_task(outer_coro())
    await asyncio.sleep(0.1)
    outer_task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await outer_task

    # Ensure the task was cancelled
    assert inner_task.cancelled() is False, "Task should not be cancelled initially"

    done_event = asyncio.Event()

    def on_done(_):
        done_event.set()

    inner_task.add_done_callback(on_done)
    await done_event.wait()


async def test_cancel_and_wait_timeout_on_slow_cleanup():
    """Test that cancel_and_wait raises TimeoutError when cleanup takes longer than max_delay"""

    CLEANUP_TIME = 2  # seconds

    async def slow_cleanup_coro():
        try:
            await asyncio.sleep(10)  # Long running task
        except asyncio.CancelledError:
            # Simulate slow cleanup that exceeds max_delay!
            await asyncio.sleep(CLEANUP_TIME)
            raise

    task = asyncio.create_task(slow_cleanup_coro())
    await asyncio.sleep(0.1)  # Let the task start

    # Cancel with a max_delay shorter than cleanup time
    with pytest.raises(TimeoutError):
        await cancel_and_shielded_wait(
            task, max_delay=CLEANUP_TIME / 10
        )  # 0.2 seconds < 2 seconds cleanup

    assert task.cancelled()


async def test_with_delay():
    @delayed_start(timedelta(seconds=0.2))
    async def decorated_awaitable() -> int:
        return 42

    assert await decorated_awaitable() == 42

    async def another_awaitable() -> int:
        return 42

    decorated_another_awaitable = delayed_start(timedelta(seconds=0.2))(
        another_awaitable
    )

    assert await decorated_another_awaitable() == 42
