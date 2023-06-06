import asyncio
from contextlib import asynccontextmanager
from typing import AsyncIterable

import pytest
from servicelib.serial_executor import BaseSerialExecutor


@asynccontextmanager
async def executor_lifecycle(
    base_serial_executor: BaseSerialExecutor,
) -> AsyncIterable[BaseSerialExecutor]:
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
        result = await executor.wait_for_result("some_str", hello=23, timeout=3)
        assert result is True

        assert (
            await executor.wait_for_result("some_str", hello="23", timeout=3) is False
        )
        assert await executor.wait_for_result(44, hello=23, timeout=3) is False


async def test_base_serial_executor_times_out():
    class TestSerialExecutor(BaseSerialExecutor):
        # pylint: disable=arguments-differ
        async def run(self) -> None:
            await asyncio.sleep(100)  # sleep for very long

    async with executor_lifecycle(TestSerialExecutor()) as executor:
        with pytest.raises(asyncio.TimeoutError):
            await executor.wait_for_result(timeout=0.1)


async def test_base_serial_executor_raises_original_error():
    class TestSerialExecutor(BaseSerialExecutor):
        # pylint: disable=arguments-differ
        async def run(self, error_reason: str) -> None:
            raise RuntimeError(error_reason)

    error_reason = "this is the expected error"
    async with executor_lifecycle(TestSerialExecutor()) as executor:
        with pytest.raises(RuntimeError, match=error_reason):
            await executor.wait_for_result(error_reason=error_reason, timeout=1)
