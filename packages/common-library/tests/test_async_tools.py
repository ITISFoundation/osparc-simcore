import asyncio
from concurrent.futures import ThreadPoolExecutor

import pytest
from common_library.async_tools import make_async


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
