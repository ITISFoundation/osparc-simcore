# ruff: noqa: SLF001, EM101, TRY003, PT011, PLR0917
# pylint: disable=no-value-for-parameter
# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import asyncio
import datetime
import logging
from typing import Literal

import pytest
from pytest_mock import MockerFixture
from servicelib.redis import RedisClientSDK
from servicelib.redis._constants import (
    SEMAPHORE_HOLDER_KEY_PREFIX,
)
from servicelib.redis._errors import SemaphoreLostError
from servicelib.redis._semaphore import (
    DistributedSemaphore,
    SemaphoreAcquisitionError,
)
from servicelib.redis._semaphore_decorator import with_limited_concurrency

pytest_simcore_core_services_selection = [
    "redis",
]
pytest_simcore_ops_services_selection = [
    "redis-commander",
]


async def test_basic_functionality(
    redis_client_sdk: RedisClientSDK,
    semaphore_name: str,
):
    call_count = 0

    @with_limited_concurrency(
        redis_client_sdk,
        key=semaphore_name,
        capacity=1,
    )
    async def limited_function():
        nonlocal call_count
        call_count += 1
        await asyncio.sleep(0.1)
        return call_count

    # Multiple concurrent calls
    tasks = [asyncio.create_task(limited_function()) for _ in range(3)]
    results = await asyncio.gather(*tasks)

    # All should complete successfully
    assert len(results) == 3
    assert all(isinstance(r, int) for r in results)


async def test_auto_renewal(
    redis_client_sdk: RedisClientSDK,
    semaphore_name: str,
    semaphore_capacity: int,
    short_ttl: datetime.timedelta,
):
    work_started = asyncio.Event()
    work_completed = asyncio.Event()

    @with_limited_concurrency(
        redis_client_sdk,
        key=semaphore_name,
        capacity=semaphore_capacity,
        ttl=short_ttl,
    )
    async def long_running_work() -> Literal["success"]:
        work_started.set()
        # Wait longer than TTL to ensure renewal works
        await asyncio.sleep(short_ttl.total_seconds() * 2)
        work_completed.set()
        return "success"

    task = asyncio.create_task(long_running_work())
    await work_started.wait()

    # Check that semaphore is being held
    temp_semaphore = DistributedSemaphore(
        redis_client=redis_client_sdk,
        key=semaphore_name,
        capacity=semaphore_capacity,
        ttl=short_ttl,
    )
    assert await temp_semaphore.get_current_count() == 1
    assert await temp_semaphore.get_available_count() == semaphore_capacity - 1

    # Wait for work to complete
    result = await task
    assert result == "success"
    assert work_completed.is_set()

    # After completion, semaphore should be released
    assert await temp_semaphore.get_current_count() == 0
    assert await temp_semaphore.get_available_count() == semaphore_capacity


async def test_auto_renewal_lose_semaphore_raises(
    redis_client_sdk: RedisClientSDK,
    semaphore_name: str,
    semaphore_capacity: int,
    short_ttl: datetime.timedelta,
):
    work_started = asyncio.Event()

    @with_limited_concurrency(
        redis_client_sdk,
        key=semaphore_name,
        capacity=semaphore_capacity,
        ttl=short_ttl,
    )
    async def work_that_should_fail() -> Literal["should not reach here"]:
        work_started.set()
        # Wait long enough for renewal to be attempted multiple times
        await asyncio.sleep(short_ttl.total_seconds() * 4)
        return "should not reach here"

    task = asyncio.create_task(work_that_should_fail())
    await work_started.wait()

    # Wait for the first renewal interval to pass
    renewal_interval = short_ttl / 3
    await asyncio.sleep(renewal_interval.total_seconds() + 1)

    # Find and delete all holder keys for this semaphore
    holder_keys = await redis_client_sdk.redis.keys(
        f"{SEMAPHORE_HOLDER_KEY_PREFIX}{semaphore_name}:*"
    )
    assert holder_keys, "Holder keys should exist before deletion"
    await redis_client_sdk.redis.delete(*holder_keys)

    with pytest.raises(SemaphoreLostError):
        await task  # This should raise the renewal failure exception


async def test_decorator_with_callable_parameters(
    redis_client_sdk: RedisClientSDK,
):
    executed_keys = []

    def get_redis_client(*args, **kwargs):
        return redis_client_sdk

    def get_key(user_id: str, resource: str) -> str:
        return f"{user_id}-{resource}"

    def get_capacity(user_id: str, resource: str) -> int:
        return 2

    @with_limited_concurrency(
        get_redis_client,
        key=get_key,
        capacity=get_capacity,
    )
    async def process_user_resource(user_id: str, resource: str):
        executed_keys.append(f"{user_id}-{resource}")
        await asyncio.sleep(0.05)

    # Test with different parameters
    await asyncio.gather(
        process_user_resource("user1", "wallet1"),
        process_user_resource("user1", "wallet2"),
        process_user_resource("user2", "wallet1"),
    )

    assert len(executed_keys) == 3
    assert "user1-wallet1" in executed_keys
    assert "user1-wallet2" in executed_keys
    assert "user2-wallet1" in executed_keys


async def test_decorator_capacity_enforcement(
    redis_client_sdk: RedisClientSDK,
    semaphore_name: str,
):
    concurrent_count = 0
    max_concurrent = 0

    @with_limited_concurrency(
        redis_client_sdk,
        key=semaphore_name,
        capacity=2,
    )
    async def limited_function():
        nonlocal concurrent_count, max_concurrent
        concurrent_count += 1
        max_concurrent = max(max_concurrent, concurrent_count)
        await asyncio.sleep(0.1)
        concurrent_count -= 1

    # Start 5 concurrent tasks
    tasks = [asyncio.create_task(limited_function()) for _ in range(5)]
    await asyncio.gather(*tasks)

    # Should never exceed capacity of 2
    assert max_concurrent <= 2


async def test_exception_handling(
    redis_client_sdk: RedisClientSDK,
    semaphore_name: str,
):
    @with_limited_concurrency(
        redis_client_sdk,
        key=semaphore_name,
        capacity=1,
    )
    async def failing_function():
        raise RuntimeError("Test exception")

    with pytest.raises(RuntimeError, match="Test exception"):
        await failing_function()

    # Semaphore should be released even after exception
    # Test by trying to acquire again
    @with_limited_concurrency(
        redis_client_sdk,
        key=semaphore_name,
        capacity=1,
    )
    async def success_function():
        return "success"

    result = await success_function()
    assert result == "success"


async def test_non_blocking_behavior(
    redis_client_sdk: RedisClientSDK,
    semaphore_name: str,
):
    # Test the blocking timeout behavior
    started_event = asyncio.Event()

    @with_limited_concurrency(
        redis_client_sdk,
        key=semaphore_name,
        capacity=1,
        blocking=True,
        blocking_timeout=datetime.timedelta(seconds=0.1),
    )
    async def limited_function() -> None:
        started_event.set()
        await asyncio.sleep(2)

    # Start first task that will hold the semaphore
    task1 = asyncio.create_task(limited_function())
    await started_event.wait()  # Wait until semaphore is actually acquired

    # Second task should timeout and raise an exception
    with pytest.raises(SemaphoreAcquisitionError):
        await limited_function()

    await task1

    # now doing the same with non-blocking should raise
    @with_limited_concurrency(
        redis_client_sdk,
        key=semaphore_name,
        capacity=1,
        blocking=False,
        blocking_timeout=datetime.timedelta(seconds=0.1),
    )
    async def limited_function_non_blocking() -> None:
        await asyncio.sleep(0.5)

    tasks = [asyncio.create_task(limited_function_non_blocking()) for _ in range(3)]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    assert len(results) == 3
    assert any(isinstance(r, SemaphoreAcquisitionError) for r in results)


async def test_user_exceptions_properly_reraised(
    redis_client_sdk: RedisClientSDK,
    semaphore_name: str,
    semaphore_capacity: int,
    short_ttl: datetime.timedelta,
    mocker: MockerFixture,
):
    class UserFunctionError(Exception):
        """Custom exception to ensure we're catching the right exception"""

    work_started = asyncio.Event()

    # Track that auto-renewal is actually happening
    from servicelib.redis._semaphore import DistributedSemaphore

    spied_renew_fct = mocker.spy(DistributedSemaphore, "reacquire")

    @with_limited_concurrency(
        redis_client_sdk,
        key=semaphore_name,
        capacity=semaphore_capacity,
        ttl=short_ttl,  # Short TTL to ensure renewal happens
    )
    async def failing_function():
        work_started.set()
        # Wait long enough for at least one renewal to happen
        await asyncio.sleep(short_ttl.total_seconds() * 0.8)
        # Then raise our custom exception
        raise UserFunctionError("User function failed intentionally")

    # Verify the exception is properly re-raised
    with pytest.raises(UserFunctionError, match="User function failed intentionally"):
        await failing_function()

    # Ensure work actually started
    assert work_started.is_set()

    # Verify auto-renewal was working (at least one renewal should have happened)
    assert (
        spied_renew_fct.call_count >= 1
    ), "Auto-renewal should have been called at least once"

    # Verify semaphore was properly released by trying to acquire it again
    test_semaphore = DistributedSemaphore(
        redis_client=redis_client_sdk,
        key=semaphore_name,
        capacity=semaphore_capacity,
        ttl=short_ttl,
    )
    assert (
        await test_semaphore.get_current_count() == 0
    ), "Semaphore should be released after exception"


async def test_cancelled_error_preserved(
    redis_client_sdk: RedisClientSDK,
    semaphore_name: str,
    semaphore_capacity: int,
):
    """Test that CancelledError is properly preserved through the decorator"""

    @with_limited_concurrency(
        redis_client_sdk,
        key=semaphore_name,
        capacity=semaphore_capacity,
    )
    async def function_raising_cancelled_error():
        raise asyncio.CancelledError

    # Verify CancelledError is preserved
    with pytest.raises(asyncio.CancelledError):
        await function_raising_cancelled_error()


@pytest.mark.heavy_load
async def test_with_large_capacity(
    redis_client_sdk: RedisClientSDK,
    semaphore_name: str,
):
    large_capacity = 100
    concurrent_count = 0
    max_concurrent = 0
    sleep_time_s = 5
    num_tasks = 1000

    @with_limited_concurrency(
        redis_client_sdk,
        key=semaphore_name,
        capacity=large_capacity,
        blocking=True,
        blocking_timeout=None,
    )
    async def limited_function() -> None:
        nonlocal concurrent_count, max_concurrent
        concurrent_count += 1
        max_concurrent = max(max_concurrent, concurrent_count)
        logging.info("Started task, current concurrent: %d", concurrent_count)
        await asyncio.sleep(sleep_time_s)
        logging.info("Done task, current concurrent: %d", concurrent_count)
        concurrent_count -= 1

    # Start tasks equal to the large capacity
    tasks = [asyncio.create_task(limited_function()) for _ in range(num_tasks)]
    done, pending = await asyncio.wait(
        tasks,
        timeout=float(num_tasks) / float(large_capacity) * 10.0 * float(sleep_time_s),
    )
    assert not pending, f"Some tasks did not complete: {len(pending)} pending"
    assert len(done) == num_tasks

    # Should never exceed the large capacity
    assert max_concurrent <= large_capacity
