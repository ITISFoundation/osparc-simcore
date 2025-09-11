# ruff: noqa: SLF001, EM101, TRY003, PT011, PLR0917
# pylint: disable=no-value-for-parameter
# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import asyncio
import datetime
from unittest import mock

import pytest
from faker import Faker
from pytest_mock import MockerFixture
from servicelib.redis import RedisClientSDK
from servicelib.redis._constants import (
    DEFAULT_SEMAPHORE_TTL,
    SEMAPHORE_HOLDER_KEY_PREFIX,
    SEMAPHORE_KEY_PREFIX,
)
from servicelib.redis._semaphore import (
    DistributedSemaphore,
    SemaphoreAcquisitionError,
    SemaphoreNotAcquiredError,
    with_limited_concurrency,
)

pytest_simcore_core_services_selection = [
    "redis",
]
pytest_simcore_ops_services_selection = [
    "redis-commander",
]


@pytest.fixture
def semaphore_name(faker: Faker) -> str:
    return faker.pystr()


@pytest.fixture
def semaphore_capacity() -> int:
    return 3


@pytest.fixture
def short_ttl() -> datetime.timedelta:
    return datetime.timedelta(seconds=1)


@pytest.fixture
def with_short_default_semaphore_ttl(
    mocker: MockerFixture,
) -> datetime.timedelta:
    short_ttl = datetime.timedelta(seconds=0.5)
    mocker.patch(
        "servicelib.redis._semaphore._DEFAULT_SEMAPHORE_TTL",
        short_ttl,
    )
    return short_ttl


async def test_semaphore_initialization(
    redis_client_sdk: RedisClientSDK,
    semaphore_name: str,
    semaphore_capacity: int,
):
    semaphore = DistributedSemaphore(
        redis_client=redis_client_sdk, key=semaphore_name, capacity=semaphore_capacity
    )

    assert semaphore.key == semaphore_name
    assert semaphore.capacity == semaphore_capacity
    assert semaphore.ttl == DEFAULT_SEMAPHORE_TTL
    assert semaphore.blocking is True
    assert semaphore._acquired is False
    assert semaphore.instance_id is not None
    assert semaphore.semaphore_key == f"{SEMAPHORE_KEY_PREFIX}{semaphore_name}"
    assert semaphore.holder_key.startswith(
        f"{SEMAPHORE_HOLDER_KEY_PREFIX}{semaphore_name}:"
    )


async def test_semaphore_invalid_capacity_raises(
    redis_client_sdk: RedisClientSDK,
    semaphore_name: str,
):
    with pytest.raises(ValueError, match="Input should be greater than 0"):
        DistributedSemaphore(
            redis_client=redis_client_sdk, key=semaphore_name, capacity=0
        )

    with pytest.raises(ValueError, match="Input should be greater than 0"):
        DistributedSemaphore(
            redis_client=redis_client_sdk, key=semaphore_name, capacity=-1
        )


async def test_semaphore_acquire_release_single(
    redis_client_sdk: RedisClientSDK,
    semaphore_name: str,
    semaphore_capacity: int,
):
    semaphore = DistributedSemaphore(
        redis_client=redis_client_sdk, key=semaphore_name, capacity=semaphore_capacity
    )

    # Initially not acquired
    assert semaphore._acquired is False

    # Acquire successfully
    result = await semaphore.acquire()
    assert result is True
    assert semaphore._acquired is True

    # Check Redis state
    assert await semaphore.get_current_count() == 1
    assert await semaphore.get_available_count() == semaphore_capacity - 1

    # Acquire again on same instance should return True immediately and keep the same count (reentrant)
    result = await semaphore.acquire()
    assert result is True
    assert await semaphore.get_current_count() == 1
    assert await semaphore.get_available_count() == semaphore_capacity - 1

    # Release
    await semaphore.release()
    assert semaphore._acquired is False
    assert await semaphore.get_current_count() == 0
    assert await semaphore.get_available_count() == semaphore_capacity


async def test_semaphore_context_manager(
    redis_client_sdk: RedisClientSDK,
    semaphore_name: str,
    semaphore_capacity: int,
):
    async with DistributedSemaphore(
        redis_client=redis_client_sdk, key=semaphore_name, capacity=semaphore_capacity
    ) as semaphore:
        assert semaphore._acquired is True
        assert await semaphore.get_current_count() == 1

    # Should be released after context
    assert semaphore._acquired is False
    assert await semaphore.get_current_count() == 0


async def test_semaphore_release_without_acquire_raises(
    redis_client_sdk: RedisClientSDK,
    semaphore_name: str,
    semaphore_capacity: int,
):
    semaphore = DistributedSemaphore(
        redis_client=redis_client_sdk, key=semaphore_name, capacity=semaphore_capacity
    )

    with pytest.raises(
        SemaphoreNotAcquiredError,
        match=f"Semaphore '{semaphore_name}' was not acquired by this instance",
    ):
        await semaphore.release()


async def test_semaphore_multiple_instances_capacity_limit(
    redis_client_sdk: RedisClientSDK,
    semaphore_name: str,
):
    capacity = 2
    semaphores = [
        DistributedSemaphore(
            redis_client=redis_client_sdk, key=semaphore_name, capacity=capacity
        )
        for _ in range(4)
    ]

    # Acquire first two should succeed
    assert await semaphores[0].acquire() is True
    assert await semaphores[1].acquire() is True

    # Third and fourth should fail in non-blocking mode
    for semaphore in semaphores[2:]:
        semaphore.blocking = False
        assert await semaphore.acquire() is False

    # Check counts
    assert await semaphores[0].get_current_count() == 2
    assert await semaphores[0].get_available_count() == 0

    # Release one
    await semaphores[0].release()
    assert await semaphores[0].get_current_count() == 1
    assert await semaphores[0].get_available_count() == 1

    # Now third can acquire
    assert await semaphores[2].acquire() is True

    # Clean up
    await semaphores[1].release()
    await semaphores[2].release()


async def test_semaphore_blocking_timeout(
    redis_client_sdk: RedisClientSDK,
    semaphore_name: str,
):
    capacity = 1
    timeout = datetime.timedelta(seconds=0.1)

    # First semaphore acquires
    async with DistributedSemaphore(
        redis_client=redis_client_sdk, key=semaphore_name, capacity=capacity
    ):
        # Second semaphore should timeout
        semaphore2 = DistributedSemaphore(
            redis_client=redis_client_sdk,
            key=semaphore_name,
            capacity=capacity,
            timeout=timeout,
        )

        with pytest.raises(
            SemaphoreAcquisitionError,
            match=f"Could not acquire semaphore '{semaphore_name}' \\(capacity: {capacity}\\)",
        ):
            await semaphore2.acquire()


async def test_semaphore_blocking_acquire_waits(
    redis_client_sdk: RedisClientSDK,
    semaphore_name: str,
):
    capacity = 1
    semaphore1 = DistributedSemaphore(
        redis_client=redis_client_sdk, key=semaphore_name, capacity=capacity
    )
    semaphore2 = DistributedSemaphore(
        redis_client=redis_client_sdk, key=semaphore_name, capacity=capacity
    )

    # First acquires immediately
    await semaphore1.acquire()

    # Second will wait
    async def delayed_release() -> None:
        await asyncio.sleep(0.1)
        await semaphore1.release()

    acquire_task = asyncio.create_task(semaphore2.acquire())
    release_task = asyncio.create_task(delayed_release())

    # Both should complete successfully
    results = await asyncio.gather(acquire_task, release_task)
    assert results[0] is True  # acquire succeeded

    await semaphore2.release()


async def test_semaphore_context_manager_with_exception(
    redis_client_sdk: RedisClientSDK,
    semaphore_name: str,
    semaphore_capacity: int,
):
    captured_semaphore: DistributedSemaphore | None = None

    async def _raising_context():
        async with DistributedSemaphore(
            redis_client=redis_client_sdk,
            key=semaphore_name,
            capacity=semaphore_capacity,
        ) as sem:
            nonlocal captured_semaphore
            captured_semaphore = sem
            assert captured_semaphore._acquired is True
            msg = "Test exception"
            raise RuntimeError(msg)

    with pytest.raises(RuntimeError, match="Test exception"):
        await _raising_context()

    # Should be released even after exception
    assert captured_semaphore is not None
    assert captured_semaphore._acquired is False
    # captured_semaphore is guaranteed to be not None by the assert above
    assert await captured_semaphore.get_current_count() == 0


async def test_semaphore_auto_renewal_via_decorator(
    redis_client_sdk: RedisClientSDK,
    semaphore_name: str,
    semaphore_capacity: int,
    short_ttl: datetime.timedelta,
):
    """Test auto-renewal functionality through the decorator (TaskGroup approach)"""
    work_started = asyncio.Event()
    work_completed = asyncio.Event()

    @with_limited_concurrency(
        redis_client_sdk,
        key=semaphore_name,
        capacity=semaphore_capacity,
        ttl=short_ttl,
    )
    async def long_running_work():
        work_started.set()
        # Wait longer than TTL to ensure renewal works
        await asyncio.sleep(short_ttl.total_seconds() * 2)
        work_completed.set()
        return "success"

    # Start the work
    task = asyncio.create_task(long_running_work())

    # Wait for work to start
    await work_started.wait()

    # Check that semaphore is being held
    temp_semaphore = DistributedSemaphore(
        redis_client=redis_client_sdk,
        key=semaphore_name,
        capacity=semaphore_capacity,
        ttl=short_ttl,
    )
    assert await temp_semaphore.get_current_count() == 1

    # Wait for work to complete
    result = await task
    assert result == "success"
    assert work_completed.is_set()

    # After completion, semaphore should be released
    assert await temp_semaphore.get_current_count() == 0


async def test_decorator_auto_renewal_failure_propagation(
    redis_client_sdk: RedisClientSDK,
    semaphore_name: str,
    semaphore_capacity: int,
    short_ttl: datetime.timedelta,
    monkeypatch: pytest.MonkeyPatch,
):
    """Test that auto-renewal failures properly propagate as exceptions in the decorator"""
    from servicelib.redis._semaphore import renew_semaphore_entry

    class RenewalFailureError(Exception):
        """Custom exception for testing renewal failures"""

    work_started = asyncio.Event()

    # Mock the renewal function to fail after first call
    call_count = 0
    original_renew = renew_semaphore_entry

    async def failing_renew_semaphore_entry(semaphore):
        nonlocal call_count
        call_count += 1
        if call_count <= 1:
            # First call succeeds
            await original_renew(semaphore)
        else:
            # Subsequent calls fail
            raise RenewalFailureError("Simulated renewal failure")

    monkeypatch.setattr(
        "servicelib.redis._semaphore.renew_semaphore_entry",
        failing_renew_semaphore_entry,
    )

    @with_limited_concurrency(
        redis_client_sdk,
        key=semaphore_name,
        capacity=semaphore_capacity,
        ttl=short_ttl,
    )
    async def work_that_should_fail():
        work_started.set()
        # Wait long enough for renewal to be attempted multiple times
        await asyncio.sleep(short_ttl.total_seconds() * 1.5)
        return "should not reach here"

    # The decorator should propagate the renewal failure
    task = asyncio.create_task(work_that_should_fail())
    await work_started.wait()  # Wait for work to start

    with pytest.raises(RenewalFailureError, match="Simulated renewal failure"):
        await task  # This should raise the renewal failure exception


async def test_semaphore_ttl_cleanup(
    redis_client_sdk: RedisClientSDK,
    semaphore_name: str,
    semaphore_capacity: int,
    short_ttl: datetime.timedelta,
):
    # Create semaphore with explicit short TTL
    semaphore = DistributedSemaphore(
        redis_client=redis_client_sdk,
        key=semaphore_name,
        capacity=semaphore_capacity,
        ttl=short_ttl,
    )

    # Manually add an expired entry
    expired_instance_id = "expired-instance"
    current_time = asyncio.get_event_loop().time()
    # Make sure it's definitely expired by using the short TTL
    expired_time = current_time - short_ttl.total_seconds() - 1

    await redis_client_sdk.redis.zadd(
        semaphore.semaphore_key, {expired_instance_id: expired_time}
    )

    # Verify the entry was added
    initial_count = await redis_client_sdk.redis.zcard(semaphore.semaphore_key)
    assert initial_count == 1

    # Current count should clean up expired entries
    count = await semaphore.get_current_count()
    assert count == 0

    # Verify expired entry was removed
    remaining = await redis_client_sdk.redis.zcard(semaphore.semaphore_key)
    assert remaining == 0


async def test_decorator_basic_functionality(
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


async def test_decorator_with_exception_handling(
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


async def test_decorator_non_blocking_behavior(
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
    async def limited_function():
        started_event.set()
        await asyncio.sleep(0.2)

    # Start first task that will hold the semaphore
    task1 = asyncio.create_task(limited_function())
    await started_event.wait()  # Wait until semaphore is actually acquired

    # Second task should timeout and raise an exception
    with pytest.raises(SemaphoreAcquisitionError):
        await limited_function()

    await task1


async def test_decorator_preserves_function_metadata(
    redis_client_sdk: RedisClientSDK,
    semaphore_name: str,
):
    @with_limited_concurrency(
        redis_client_sdk,
        key=semaphore_name,
        capacity=1,
    )
    async def documented_function(arg1: str, arg2: int) -> str:
        """Test function with documentation"""
        return f"{arg1}-{arg2}"

    assert documented_function.__name__ == "documented_function"
    assert documented_function.__doc__ == "Test function with documentation"

    result = await documented_function("test", 42)
    assert result == "test-42"


async def test_redis_connection_failure_during_acquire(
    redis_client_sdk: RedisClientSDK,
    semaphore_name: str,
    semaphore_capacity: int,
):
    semaphore = DistributedSemaphore(
        redis_client=redis_client_sdk,
        key=semaphore_name,
        capacity=semaphore_capacity,
        blocking=False,
    )

    # Mock Redis to raise an exception
    with mock.patch.object(
        redis_client_sdk.redis, "zcard", side_effect=Exception("Redis error")
    ):
        result = await semaphore.acquire()
        assert result is False


async def test_multiple_semaphores_different_keys(
    redis_client_sdk: RedisClientSDK,
    faker: Faker,
):
    """Test that semaphores with different keys don't interfere"""
    key1 = faker.pystr()
    key2 = faker.pystr()
    capacity = 1

    sem1 = DistributedSemaphore(
        redis_client=redis_client_sdk, key=key1, capacity=capacity
    )
    sem2 = DistributedSemaphore(
        redis_client=redis_client_sdk, key=key2, capacity=capacity
    )

    # Both should be able to acquire since they have different keys
    assert await sem1.acquire() is True
    assert await sem2.acquire() is True

    await sem1.release()
    await sem2.release()


async def test_semaphore_acquire_after_release(
    redis_client_sdk: RedisClientSDK,
    semaphore_name: str,
    semaphore_capacity: int,
):
    """Test that semaphore can be acquired again after release"""
    semaphore = DistributedSemaphore(
        redis_client=redis_client_sdk, key=semaphore_name, capacity=semaphore_capacity
    )

    # Acquire, release, acquire again
    await semaphore.acquire()
    await semaphore.release()

    result = await semaphore.acquire()
    assert result is True
    assert semaphore._acquired is True

    await semaphore.release()
