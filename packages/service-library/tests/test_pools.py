from asyncio import BaseEventLoop
from concurrent.futures import ProcessPoolExecutor

import pytest
from servicelib.pools import non_blocking_process_pool_executor


def return_int_one() -> int:
    return 1


@pytest.mark.asyncio
async def test_default_thread_pool_executor(loop: BaseEventLoop) -> None:
    assert await loop.run_in_executor(None, return_int_one) == 1


@pytest.mark.asyncio
async def test_blocking_process_pool_executor(loop: BaseEventLoop) -> None:
    assert await loop.run_in_executor(ProcessPoolExecutor(), return_int_one) == 1


@pytest.mark.asyncio
async def test_non_blocking_process_pool_executor(loop: BaseEventLoop) -> None:
    with non_blocking_process_pool_executor() as executor:
        assert await loop.run_in_executor(executor, return_int_one) == 1
