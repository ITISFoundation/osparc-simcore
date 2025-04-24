"""Tests for database result utility functions"""

from typing import Any

from simcore_postgres_database.utils_results import maybe_await


async def test_maybe_await_with_coroutine():
    """Test maybe_await with an async function"""

    async def async_value():
        return 42

    result = await maybe_await(async_value())
    assert result == 42


async def test_maybe_await_with_direct_value():
    """Test maybe_await with a direct value"""
    value = 42
    result = await maybe_await(value)
    assert result == 42


async def test_maybe_await_with_none():
    """Test maybe_await with None value"""
    result = await maybe_await(None)
    assert result is None


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
