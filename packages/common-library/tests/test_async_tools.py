import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import pytest
from common_library.async_tools import make_async, maybe_await


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


"""Tests for database result utility functions"""


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

        async def fetchone(self) -> Any:
            return {"id": 1, "name": "test"}

    class SyncResultProxy:
        """Mock sync result proxy (asyncpg style)"""

        def fetchone(self) -> Any:
            return {"id": 2, "name": "test2"}

    async_result = await maybe_await(AsyncResultProxy().fetchone())
    assert async_result == {"id": 1, "name": "test"}

    sync_result = await maybe_await(SyncResultProxy().fetchone())
    assert sync_result == {"id": 2, "name": "test2"}
