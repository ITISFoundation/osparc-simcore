import asyncio
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from typing import Any

import pytest
from common_library.async_tools import (
    cancel_wait_task,
    delayed_start,
    iter_with_timeout,
    make_async,
    maybe_await,
)


@make_async()
def sync_function(x: int, y: int) -> int:
    return x + y


@make_async()
def sync_function_with_exception() -> None:
    msg = "This is an error!"
    raise ValueError(msg)


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
    SLEEP_TIME = 5  # seconds

    async def coro():
        try:
            state["started"] = True
            await asyncio.sleep(SLEEP_TIME)
        except asyncio.CancelledError:
            state["cancelled"] = True
            raise
        finally:
            state["cleaned_up"] = True

    task = asyncio.create_task(coro())
    await asyncio.sleep(0.1)  # Let coro start

    start = time.time()
    await cancel_wait_task(task)

    elapsed = time.time() - start
    assert elapsed < SLEEP_TIME, "Task should be cancelled quickly"
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

    async def coro():
        try:
            await asyncio.sleep(4)
        except asyncio.CancelledError:
            await asyncio.sleep(1)  # simulate cleanup
            raise

    inner_task = asyncio.create_task(coro())

    async def outer_coro():
        try:
            await cancel_wait_task(inner_task)
        except asyncio.CancelledError:
            assert not inner_task.cancelled(), "Internal Task DOES NOT RAISE CancelledError"
            raise

    # Cancel the wrapper after a short delay
    outer_task = asyncio.create_task(outer_coro())
    await asyncio.sleep(0.1)
    outer_task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await outer_task

    # Ensure the task was cancelled
    assert inner_task.cancelled() is False, "Task should not be cancelled initially"

    done_event = asyncio.Event()

    def on_done(_):
        done_event.set()

    inner_task.add_done_callback(on_done)
    await done_event.wait()


async def test_cancel_and_wait_timeout_on_slow_cleanup():
    """Test that cancel_and_wait raises TimeoutError when cleanup takes longer than max_delay"""

    CLEANUP_TIME = 2  # seconds

    async def slow_cleanup_coro():
        try:
            await asyncio.sleep(10)  # Long running task
        except asyncio.CancelledError:
            # Simulate slow cleanup that exceeds max_delay!
            await asyncio.sleep(CLEANUP_TIME)
            raise

    task = asyncio.create_task(slow_cleanup_coro())
    await asyncio.sleep(0.1)  # Let the task start

    # Cancel with a max_delay shorter than cleanup time
    with pytest.raises(TimeoutError):
        await cancel_wait_task(task, max_delay=CLEANUP_TIME / 10)  # 0.2 seconds < 2 seconds cleanup

    assert task.cancelling() == 1

    assert not task.cancelled()


async def test_cancel_and_wait_with_raising_during_cleanup():
    async def raising_cleanup_coro():
        try:
            await asyncio.sleep(10)  # Long running task
        except asyncio.CancelledError as exc:
            # Simulate cleanup that raises an exception
            msg = "Error during cleanup"
            raise RuntimeError(msg) from exc

    task = asyncio.create_task(raising_cleanup_coro())
    await asyncio.sleep(0.1)  # Let the task start

    # Cancel and wait, expecting the RuntimeError to be logged but not propagated
    with pytest.raises(RuntimeError):
        await cancel_wait_task(task, max_delay=None)  # 1 second timeout

    assert task.cancelling() == 1
    assert not task.cancelled()


async def test_with_delay():
    @delayed_start(timedelta(seconds=0.2))
    async def decorated_awaitable() -> int:
        return 42

    assert await decorated_awaitable() == 42

    async def another_awaitable() -> int:
        return 42

    decorated_another_awaitable = delayed_start(timedelta(seconds=0.2))(another_awaitable)

    assert await decorated_another_awaitable() == 42


async def test_iter_with_timeout_yields_all_items():
    """Test that iter_with_timeout yields all items from iterator within timeout"""

    async def async_generator():
        for i in range(5):
            yield i

    items = [item async for item in iter_with_timeout(async_generator(), per_iteration_timeout=timedelta(seconds=1))]

    assert items == [0, 1, 2, 3, 4]


async def test_iter_with_timeout_raises_on_slow_iteration():
    """Test that iter_with_timeout raises TimeoutError when iteration exceeds timeout"""

    async def slow_generator():
        yield 1
        await asyncio.sleep(2)  # This exceeds the timeout
        yield 2

    with pytest.raises(asyncio.TimeoutError):
        async for _ in iter_with_timeout(slow_generator(), per_iteration_timeout=timedelta(seconds=0.5)):
            pass


async def test_iter_with_timeout_handles_empty_iterator():
    """Test that iter_with_timeout works with empty iterators"""

    async def empty_generator():
        return
        yield  # pylint: disable=unreachable

    items = [item async for item in iter_with_timeout(empty_generator(), per_iteration_timeout=timedelta(seconds=1))]

    assert items == []


async def test_iter_with_timeout_calls_aclose():
    """Test that iter_with_timeout calls aclose on the iterator"""

    cleanup_called = False

    async def generator_with_cleanup():
        try:
            for i in range(3):
                yield i
        finally:
            nonlocal cleanup_called
            cleanup_called = True

    items = [
        item async for item in iter_with_timeout(generator_with_cleanup(), per_iteration_timeout=timedelta(seconds=1))
    ]

    assert items == [0, 1, 2]
    assert cleanup_called


async def test_iter_with_timeout_calls_aclose_on_exception():
    """Test that iter_with_timeout calls aclose even when an exception occurs"""

    cleanup_called = False

    async def slow_generator():
        try:
            yield 1
            await asyncio.sleep(2)  # Exceeds timeout
            yield 2
        finally:
            nonlocal cleanup_called
            cleanup_called = True

    with pytest.raises(asyncio.TimeoutError):
        async for _ in iter_with_timeout(slow_generator(), per_iteration_timeout=timedelta(seconds=0.5)):
            pass

    assert cleanup_called


async def test_iter_with_timeout_with_large_timeout():
    """Test that iter_with_timeout works with very large timeouts"""

    async def generator():
        for i in range(10):
            yield i
            await asyncio.sleep(0.01)

    items = [item async for item in iter_with_timeout(generator(), per_iteration_timeout=timedelta(seconds=60))]

    assert items == list(range(10))


async def test_iter_with_timeout_cancellation():
    """Test that iter_with_timeout handles cancellation properly"""

    async def generator():
        for i in range(100):
            yield i
            await asyncio.sleep(0.01)

    items = []

    async def consume_with_cancel():
        nonlocal items
        try:
            async for item in iter_with_timeout(generator(), per_iteration_timeout=timedelta(seconds=1)):
                items.append(item)
                if len(items) == 5:
                    raise asyncio.CancelledError  # noqa: TRY301
        except asyncio.CancelledError:
            pass

    await consume_with_cancel()
    assert len(items) == 5


async def test_iter_with_timeout_with_custom_async_iterator():
    """Test iter_with_timeout with a custom async iterator class"""

    class CustomAsyncIterator:
        def __init__(self, max_items: int):
            self.max_items = max_items
            self.current = 0
            self.closed = False

        def __aiter__(self):
            return self

        async def __anext__(self):
            if self.current >= self.max_items:
                raise StopAsyncIteration
            self.current += 1
            await asyncio.sleep(0.01)
            return self.current - 1

        async def aclose(self):
            self.closed = True

    iterator = CustomAsyncIterator(5)
    items = [item async for item in iter_with_timeout(iterator, per_iteration_timeout=timedelta(seconds=1))]

    assert items == [0, 1, 2, 3, 4]
    assert iterator.closed


async def test_iter_with_timeout_without_aclose_method():
    """Test iter_with_timeout with iterators that don't have aclose method"""

    class SimpleAsyncIterator:
        def __init__(self, max_items: int):
            self.max_items = max_items
            self.current = 0

        def __aiter__(self):
            return self

        async def __anext__(self):
            if self.current >= self.max_items:
                raise StopAsyncIteration
            self.current += 1
            return self.current - 1

    iterator = SimpleAsyncIterator(3)
    items = [item async for item in iter_with_timeout(iterator, per_iteration_timeout=timedelta(seconds=1))]

    assert items == [0, 1, 2]
