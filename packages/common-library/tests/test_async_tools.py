import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import pytest
from common_library.async_tools import cancel_and_wait, make_async, maybe_await


@make_async()
def sync_function(x: int, y: int) -> int:
    return x + y


@make_async()
def sync_function_with_exception() -> None:
    raise ValueError("This is an error!")


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

    async def coro():
        try:
            state["started"] = True
            await asyncio.sleep(5)
        except asyncio.CancelledError:
            state["cancelled"] = True
            raise
        finally:
            state["cleaned_up"] = True

    task = asyncio.create_task(coro())
    await asyncio.sleep(0.1)  # Let coro start

    await cancel_and_wait(task)

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

    async def inner_coro():
        try:
            await asyncio.sleep(10)
        except asyncio.CancelledError:
            await asyncio.sleep(0.1)  # simulate cleanup
            raise

    task = asyncio.create_task(inner_coro())

    async def outer_coro():
        await cancel_and_wait(task)

    # Cancel the wrapper after a short delay
    outer_task = asyncio.create_task(outer_coro())
    await asyncio.sleep(0.1)
    outer_task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await outer_task

    assert task.cancelled()
