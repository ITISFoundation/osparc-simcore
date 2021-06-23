from asyncio import BaseEventLoop

from servicelib.pools import non_blocking_process_pool_executor
from concurrent.futures import ProcessPoolExecutor
import pytest
from concurrent.futures import Executor


def return_int_one() -> int:
    return 1


async def _assert_works_with_executor(
    loop: BaseEventLoop, executor: Executor = None
) -> None:
    result = await loop.run_in_executor(executor, return_int_one)
    assert result == 1


@pytest.mark.asyncio
async def test_default_thread_pool_executor(loop: BaseEventLoop) -> None:
    await _assert_works_with_executor(loop)


@pytest.mark.asyncio
async def test_blocking_process_pool_executor(loop: BaseEventLoop) -> None:
    with ProcessPoolExecutor() as executor:
        await _assert_works_with_executor(loop, executor)


@pytest.mark.asyncio
async def test_non_blocking_process_pool_executor(loop: BaseEventLoop) -> None:
    with non_blocking_process_pool_executor() as executor:
        await _assert_works_with_executor(loop, executor)
