import asyncio
from concurrent.futures import ProcessPoolExecutor

from servicelib.pools import (
    non_blocking_process_pool_executor,
    non_blocking_thread_pool_executor,
)


def return_int_one() -> int:
    return 1


async def test_default_thread_pool_executor() -> None:
    assert await asyncio.get_running_loop().run_in_executor(None, return_int_one) == 1


async def test_blocking_process_pool_executor() -> None:
    assert (
        await asyncio.get_running_loop().run_in_executor(
            ProcessPoolExecutor(), return_int_one
        )
        == 1
    )


async def test_non_blocking_process_pool_executor() -> None:
    with non_blocking_process_pool_executor() as executor:
        assert (
            await asyncio.get_running_loop().run_in_executor(executor, return_int_one)
            == 1
        )


async def test_same_pool_instances() -> None:
    with non_blocking_process_pool_executor() as first, non_blocking_process_pool_executor() as second:
        assert first == second


async def test_different_pool_instances() -> None:
    with non_blocking_process_pool_executor(
        max_workers=1
    ) as first, non_blocking_process_pool_executor() as second:
        assert first != second


async def test_non_blocking_thread_pool_executor() -> None:
    with non_blocking_thread_pool_executor() as executor:
        assert (
            await asyncio.get_running_loop().run_in_executor(executor, return_int_one)
            == 1
        )


async def test_same_thread_pool_instances() -> None:
    with non_blocking_thread_pool_executor() as first, non_blocking_thread_pool_executor() as second:
        assert first == second


async def test_different_thread_pool_instances() -> None:
    with non_blocking_thread_pool_executor(
        max_workers=1
    ) as first, non_blocking_thread_pool_executor() as second:
        assert first != second
