import asyncio
from contextlib import asynccontextmanager
from copy import copy
from typing import AsyncIterator, Final

import pytest
from pydantic import NonNegativeInt
from servicelib.serial_executor import BaseSerialExecutor

SHARED_CONTEXT_KEY: Final[str] = "share"


@asynccontextmanager
async def executor_lifecycle(
    base_serial_executor: BaseSerialExecutor,
) -> AsyncIterator[BaseSerialExecutor]:
    await base_serial_executor.start()
    yield base_serial_executor
    await base_serial_executor.stop()


async def test_base_serial_executor():
    class TestSerialExecutor(BaseSerialExecutor):
        # pylint: disable=arguments-differ
        async def run(self, positional_arg: str, hello: int = 2) -> bool:
            if type(positional_arg) != str:
                return False
            if type(hello) != int:
                return False
            return type(positional_arg + f"{hello}") == str

    async with executor_lifecycle(TestSerialExecutor()) as executor:
        result = await executor.wait_for_result(
            "some_str", hello=23, timeout=3, context_key=SHARED_CONTEXT_KEY
        )
        assert result is True

        assert (
            await executor.wait_for_result(
                "some_str", hello="23", timeout=3, context_key=SHARED_CONTEXT_KEY
            )
            is False
        )
        assert (
            await executor.wait_for_result(
                44, hello=23, timeout=3, context_key=SHARED_CONTEXT_KEY
            )
            is False
        )


async def test_base_serial_executor_times_out():
    class TestSerialExecutor(BaseSerialExecutor):
        # pylint: disable=arguments-differ
        async def run(self) -> None:
            await asyncio.sleep(100)  # sleep for very long

    async with executor_lifecycle(TestSerialExecutor()) as executor:
        with pytest.raises(asyncio.TimeoutError):
            await executor.wait_for_result(timeout=0.1, context_key=SHARED_CONTEXT_KEY)


async def test_base_serial_executor_raises_original_error():
    class TestSerialExecutor(BaseSerialExecutor):
        # pylint: disable=arguments-differ
        async def run(self, error_reason: str) -> None:
            raise RuntimeError(error_reason)

    error_reason = "this is the expected error"
    async with executor_lifecycle(TestSerialExecutor()) as executor:
        with pytest.raises(RuntimeError, match=error_reason):
            await executor.wait_for_result(
                error_reason=error_reason, timeout=1, context_key=SHARED_CONTEXT_KEY
            )


async def test_base_serial_executor_same_context_key_parallel():
    shared_counter: int = 0
    counter_values: list[int] = []

    ITERATIONS: NonNegativeInt = 100

    class TestSerialExecutor(BaseSerialExecutor):
        # pylint: disable=arguments-differ
        async def run(self) -> None:
            nonlocal shared_counter
            shared_counter += 1

            await asyncio.sleep(0)
            counter_values.append(copy(shared_counter))
            await asyncio.sleep(0)

            shared_counter -= 1

    async with executor_lifecycle(
        TestSerialExecutor(polling_interval=0.001)
    ) as executor:
        # run in parallel
        await asyncio.gather(
            *[
                executor.wait_for_result(timeout=10, context_key=SHARED_CONTEXT_KEY)
                for _ in range(ITERATIONS)
            ]
        )

        # race condition is avoided amd produces the expected results
        assert counter_values == [1] * ITERATIONS


async def test_base_serial_executor_different_context_key_parallel():
    shared_counter: int = 0
    counter_values: list[int] = []

    ITERATIONS: NonNegativeInt = 1000

    class TestSerialExecutor(BaseSerialExecutor):
        # pylint: disable=arguments-differ
        async def run(self) -> None:
            nonlocal shared_counter
            shared_counter += 1

            await asyncio.sleep(0)
            counter_values.append(copy(shared_counter))
            await asyncio.sleep(0)

            shared_counter -= 1

    async with executor_lifecycle(
        TestSerialExecutor(polling_interval=0.001)
    ) as executor:
        # run in parallel
        await asyncio.gather(
            *[
                executor.wait_for_result(timeout=10, context_key=f"key_{x}")
                for x in range(ITERATIONS)
            ]
        )

        # here the race condition is not avoided
        assert counter_values != [1] * ITERATIONS
