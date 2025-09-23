# ruff: noqa: SLF001, EM101, TRY003, PT011, PLR0917
# pylint: disable=no-value-for-parameter
# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import asyncio
import datetime

import pytest
from faker import Faker
from pytest_mock import MockerFixture
from servicelib.redis import RedisClientSDK
from servicelib.redis._constants import (
    DEFAULT_SEMAPHORE_TTL,
    SEMAPHORE_KEY_PREFIX,
)
from servicelib.redis._errors import SemaphoreLostError
from servicelib.redis._semaphore import (
    DistributedSemaphore,
    SemaphoreAcquisitionError,
    SemaphoreNotAcquiredError,
    distributed_semaphore,
)
from servicelib.redis._utils import handle_redis_returns_union_types

pytest_simcore_core_services_selection = [
    "redis",
]
pytest_simcore_ops_services_selection = [
    "redis-commander",
]


@pytest.fixture
def with_short_default_semaphore_ttl(
    mocker: MockerFixture,
) -> datetime.timedelta:
    short_ttl = datetime.timedelta(seconds=2)
    mocker.patch(
        "servicelib.redis._semaphore.DEFAULT_SEMAPHORE_TTL",
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
    assert semaphore.instance_id is not None
    assert semaphore.semaphore_key == f"{SEMAPHORE_KEY_PREFIX}{semaphore_name}"
    assert semaphore.tokens_key.startswith(f"{semaphore.semaphore_key}:")
    assert semaphore.holders_set.startswith(f"{semaphore.semaphore_key}:")
    assert semaphore.holder_key.startswith(f"{semaphore.semaphore_key}:")


async def test_invalid_semaphore_initialization(
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

    with pytest.raises(ValueError, match="TTL must be positive"):
        DistributedSemaphore(
            redis_client=redis_client_sdk,
            key=semaphore_name,
            capacity=1,
            ttl=datetime.timedelta(seconds=0),
        )
    with pytest.raises(ValueError, match="TTL must be positive"):
        DistributedSemaphore(
            redis_client=redis_client_sdk,
            key=semaphore_name,
            capacity=1,
            ttl=datetime.timedelta(seconds=0.5),
        )
    with pytest.raises(ValueError, match="Timeout must be positive"):
        DistributedSemaphore(
            redis_client=redis_client_sdk,
            key=semaphore_name,
            capacity=1,
            ttl=datetime.timedelta(seconds=10),
            blocking=True,
            blocking_timeout=datetime.timedelta(seconds=0),
        )


async def _assert_semaphore_redis_state(
    redis_client_sdk: RedisClientSDK,
    semaphore: DistributedSemaphore,
    *,
    expected_count: int,
    expected_free_tokens: int,
    expected_expired: bool = False,
):
    """Helper to assert the internal Redis state of the semaphore"""
    holders = await handle_redis_returns_union_types(
        redis_client_sdk.redis.smembers(semaphore.holders_set)
    )
    assert len(holders) == expected_count
    if expected_count > 0:
        assert semaphore.instance_id in holders
        holder_key_exists = await redis_client_sdk.redis.exists(semaphore.holder_key)
        if expected_expired:
            assert holder_key_exists == 0
        else:
            assert holder_key_exists == 1
    tokens = await handle_redis_returns_union_types(
        redis_client_sdk.redis.lrange(semaphore.tokens_key, 0, -1)
    )
    assert len(tokens) == expected_free_tokens


async def test_semaphore_acquire_release_basic(
    redis_client_sdk: RedisClientSDK,
    semaphore_name: str,
    semaphore_capacity: int,
    with_short_default_semaphore_ttl: datetime.timedelta,
):
    semaphore = DistributedSemaphore(
        redis_client=redis_client_sdk,
        key=semaphore_name,
        capacity=semaphore_capacity,
        ttl=with_short_default_semaphore_ttl,
    )

    # Initially not acquired
    assert await semaphore.current_count() == 0
    assert await semaphore.size() == semaphore_capacity
    assert await semaphore.is_acquired() is False
    await _assert_semaphore_redis_state(
        redis_client_sdk,
        semaphore,
        expected_count=0,
        expected_free_tokens=semaphore_capacity,
    )

    # Acquire
    result = await semaphore.acquire()
    assert result is True
    assert await semaphore.current_count() == 1
    assert await semaphore.size() == semaphore_capacity - 1
    assert await semaphore.is_acquired() is True
    await _assert_semaphore_redis_state(
        redis_client_sdk,
        semaphore,
        expected_count=1,
        expected_free_tokens=semaphore_capacity - 1,
    )

    # Acquire again on same instance should return True immediately and keep the same count (reentrant)
    result = await semaphore.acquire()
    assert result is True
    assert await semaphore.current_count() == 1
    assert await semaphore.size() == semaphore_capacity - 1
    assert await semaphore.is_acquired() is True
    await _assert_semaphore_redis_state(
        redis_client_sdk,
        semaphore,
        expected_count=1,
        expected_free_tokens=semaphore_capacity - 1,
    )

    # reacquire should just work
    await semaphore.reacquire()
    assert await semaphore.current_count() == 1
    assert await semaphore.size() == semaphore_capacity - 1
    assert await semaphore.is_acquired() is True
    await _assert_semaphore_redis_state(
        redis_client_sdk,
        semaphore,
        expected_count=1,
        expected_free_tokens=semaphore_capacity - 1,
    )

    # Release
    await semaphore.release()
    assert await semaphore.current_count() == 0
    assert await semaphore.size() == semaphore_capacity
    assert await semaphore.is_acquired() is False
    await _assert_semaphore_redis_state(
        redis_client_sdk,
        semaphore,
        expected_count=0,
        expected_free_tokens=semaphore_capacity,
    )

    # reacquire after release should fail
    with pytest.raises(SemaphoreNotAcquiredError):
        await semaphore.reacquire()
    await _assert_semaphore_redis_state(
        redis_client_sdk,
        semaphore,
        expected_count=0,
        expected_free_tokens=semaphore_capacity,
    )

    # so does release again
    with pytest.raises(SemaphoreNotAcquiredError):
        await semaphore.release()
    await _assert_semaphore_redis_state(
        redis_client_sdk,
        semaphore,
        expected_count=0,
        expected_free_tokens=semaphore_capacity,
    )


async def test_semaphore_acquire_release_with_ttl_expiry(
    redis_client_sdk: RedisClientSDK,
    semaphore_name: str,
    semaphore_capacity: int,
    with_short_default_semaphore_ttl: datetime.timedelta,
):
    semaphore = DistributedSemaphore(
        redis_client=redis_client_sdk,
        key=semaphore_name,
        capacity=semaphore_capacity,
        ttl=with_short_default_semaphore_ttl,
    )
    await semaphore.acquire()
    assert await semaphore.current_count() == 1
    assert await semaphore.size() == semaphore_capacity - 1
    await _assert_semaphore_redis_state(
        redis_client_sdk,
        semaphore,
        expected_count=1,
        expected_free_tokens=semaphore_capacity - 1,
    )

    # wait for TTL to expire
    await asyncio.sleep(with_short_default_semaphore_ttl.total_seconds() + 0.1)
    await _assert_semaphore_redis_state(
        redis_client_sdk,
        semaphore,
        expected_count=1,
        expected_free_tokens=semaphore_capacity - 1,
        expected_expired=True,
    )

    # TTL expired, reacquire should fail
    with pytest.raises(SemaphoreLostError):
        await semaphore.reacquire()
    await _assert_semaphore_redis_state(
        redis_client_sdk,
        semaphore,
        expected_count=1,
        expected_free_tokens=semaphore_capacity - 1,
        expected_expired=True,
    )
    # and release should also fail
    with pytest.raises(SemaphoreLostError):
        await semaphore.release()
    await _assert_semaphore_redis_state(
        redis_client_sdk,
        semaphore,
        expected_count=0,
        expected_free_tokens=semaphore_capacity,
    )

    # and release again should also fail with different error
    with pytest.raises(SemaphoreNotAcquiredError):
        await semaphore.release()
    await _assert_semaphore_redis_state(
        redis_client_sdk,
        semaphore,
        expected_count=0,
        expected_free_tokens=semaphore_capacity,
    )


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
    assert await semaphores[0].is_acquired() is True
    await _assert_semaphore_redis_state(
        redis_client_sdk,
        semaphores[0],
        expected_count=1,
        expected_free_tokens=capacity - 1,
    )
    assert await semaphores[1].is_acquired() is False
    for sem in semaphores[:4]:
        assert await sem.current_count() == 1
        assert await sem.size() == capacity - 1

    # acquire second
    assert await semaphores[1].acquire() is True
    for sem in semaphores[:2]:
        assert await sem.is_acquired() is True
        assert await sem.current_count() == 2
        assert await sem.size() == capacity - 2
        await _assert_semaphore_redis_state(
            redis_client_sdk,
            sem,
            expected_count=2,
            expected_free_tokens=capacity - 2,
        )

    # Third and fourth should fail in non-blocking mode
    for sem in semaphores[2:]:
        sem.blocking = False
        assert await sem.acquire() is False
        assert await sem.is_acquired() is False
        assert await sem.current_count() == 2
        assert await sem.size() == capacity - 2

    # Release one
    await semaphores[0].release()
    assert await semaphores[0].is_acquired() is False
    for sem in semaphores[:4]:
        assert await sem.current_count() == 1
        assert await sem.size() == capacity - 1

    # Now third can acquire
    assert await semaphores[2].acquire() is True
    for sem in semaphores[:4]:
        assert await sem.current_count() == 2
        assert await sem.size() == capacity - 2

    # Clean up
    await semaphores[1].release()
    await semaphores[2].release()


async def test_semaphore_context_manager(
    redis_client_sdk: RedisClientSDK,
    semaphore_name: str,
):
    capacity = 1
    timeout = datetime.timedelta(seconds=0.1)

    # First semaphore acquires
    async with distributed_semaphore(
        redis_client=redis_client_sdk,
        key=semaphore_name,
        capacity=capacity,
    ) as semaphore1:
        assert await semaphore1.is_acquired() is True
        assert await semaphore1.current_count() == 1
        assert await semaphore1.size() == 0
        await _assert_semaphore_redis_state(
            redis_client_sdk,
            semaphore1,
            expected_count=1,
            expected_free_tokens=0,
        )

        # Second semaphore should timeout
        semaphore2 = DistributedSemaphore(
            redis_client=redis_client_sdk,
            key=semaphore_name,
            capacity=capacity,
            blocking_timeout=timeout,
        )

        with pytest.raises(
            SemaphoreAcquisitionError,
            match=f"Could not acquire semaphore '{semaphore_name}' by this instance",
        ):
            await semaphore2.acquire()

        # now try infinite timeout
        semaphore3 = DistributedSemaphore(
            redis_client=redis_client_sdk,
            key=semaphore_name,
            capacity=capacity,
            blocking_timeout=None,  # wait forever
        )
        acquire_task = asyncio.create_task(semaphore3.acquire())
        await asyncio.sleep(5)  # give some time to start acquiring
        assert not acquire_task.done()


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


@pytest.mark.parametrize(
    "exception",
    [RuntimeError, asyncio.CancelledError],
    ids=str,
)
async def test_semaphore_context_manager_with_exception(
    redis_client_sdk: RedisClientSDK,
    semaphore_name: str,
    semaphore_capacity: int,
    exception: type[Exception | asyncio.CancelledError],
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
            raise exception("Test")

    with pytest.raises(exception, match="Test"):
        await _raising_context()

    # Should be released even after exception
    assert captured_semaphore is not None
    # captured_semaphore is guaranteed to be not None by the assert above
    assert await captured_semaphore.current_count() == 0


async def test_multiple_semaphores_different_keys(
    redis_client_sdk: RedisClientSDK,
    faker: Faker,
):
    """Test that semaphores with different keys don't interfere"""
    key1 = faker.pystr()
    key2 = faker.pystr()
    capacity = 1

    async with (
        DistributedSemaphore(
            redis_client=redis_client_sdk, key=key1, capacity=capacity
        ),
        DistributedSemaphore(
            redis_client=redis_client_sdk, key=key2, capacity=capacity
        ),
    ):
        ...
