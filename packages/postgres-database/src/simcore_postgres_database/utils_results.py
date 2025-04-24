"""Utilities for handling database results from both aiopg and asyncpg backends.

Handles the difference between async (aiopg) and sync (asyncpg) result methods.
"""

from collections.abc import Awaitable
from typing import TypeVar, cast, overload

T = TypeVar("T")


@overload
async def maybe_await(obj: Awaitable[T]) -> T: ...


@overload
async def maybe_await(obj: T) -> T: ...


async def maybe_await(obj: T | Awaitable[T]) -> T:
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
    if hasattr(obj, "__await__"):
        return await cast(Awaitable[T], obj)
    return cast(T, obj)
