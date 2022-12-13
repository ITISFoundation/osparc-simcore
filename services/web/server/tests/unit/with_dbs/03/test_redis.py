# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import asyncio
import datetime

import pytest
import redis
import redis.asyncio as aioredis
from faker import Faker
from redis.asyncio.lock import Lock
from servicelib.background_task import periodic_task


async def test_aioredis(redis_client: aioredis.Redis, faker: Faker):
    key = faker.pystr()
    value = faker.pystr()
    await redis_client.set(key, value)
    val = await redis_client.get(key)
    assert val == value


async def test_lock_acquisition(redis_client: aioredis.Redis, faker: Faker):
    lock_name = faker.pystr()
    lock = redis_client.lock(lock_name)
    assert not await lock.locked()

    # Try to acquire the lock:
    lock_acquired = await lock.acquire(blocking=False)
    assert lock_acquired is True
    assert await lock.locked() is True
    assert await lock.owned() is True
    with pytest.raises(redis.exceptions.LockError):
        # a lock with no timeout cannot be reacquired
        await lock.reacquire()
    with pytest.raises(redis.exceptions.LockError):
        # a lock with no timeout cannot be extended
        await lock.extend(2)

    # try to acquire the lock a second time
    same_lock = redis_client.lock(lock_name)
    assert await same_lock.locked() is True
    assert await same_lock.owned() is False
    assert await same_lock.acquire(blocking=False) is False

    # now release the lock
    await lock.release()
    assert not await lock.locked()
    assert not await lock.owned()


async def test_lock_context_manager(redis_client: aioredis.Redis, faker: Faker):
    lock_name = faker.pystr()
    lock = redis_client.lock(lock_name)
    assert not await lock.locked()

    async with lock:
        assert await lock.locked()
        assert await lock.owned()
        with pytest.raises(redis.exceptions.LockError):
            # a lock with no timeout cannot be reacquired
            await lock.reacquire()

        with pytest.raises(redis.exceptions.LockError):
            # a lock with no timeout cannot be extended
            await lock.extend(2)

        # try to acquire the lock a second time
        same_lock = redis_client.lock(lock_name, blocking_timeout=1)
        assert await same_lock.locked()
        assert not await same_lock.owned()
        assert await same_lock.acquire() == False
        with pytest.raises(redis.exceptions.LockError):
            async with same_lock:
                ...
    assert not await lock.locked()


@pytest.fixture
def lock_timeout() -> datetime.timedelta:
    return datetime.timedelta(seconds=2)


async def test_lock_with_ttl(
    redis_client: aioredis.Redis, faker: Faker, lock_timeout: datetime.timedelta
):
    ttl_lock = redis_client.lock(faker.pystr(), timeout=lock_timeout.total_seconds())
    assert not await ttl_lock.locked()

    with pytest.raises(redis.exceptions.LockNotOwnedError):
        # this raises as the lock is lost
        async with ttl_lock:
            assert await ttl_lock.locked()
            assert await ttl_lock.owned()
            await asyncio.sleep(2 * lock_timeout.total_seconds())
            assert not await ttl_lock.locked()


async def test_lock_with_auto_extent(
    redis_client: aioredis.Redis, faker: Faker, lock_timeout: datetime.timedelta
):
    ttl_lock = redis_client.lock(faker.pystr(), timeout=lock_timeout.total_seconds())
    assert not await ttl_lock.locked()

    async def _auto_extend_lock(lock: Lock) -> None:
        assert await lock.reacquire() is True

    async with ttl_lock, periodic_task(
        _auto_extend_lock,
        interval=0.6 * lock_timeout,
        task_name=f"{ttl_lock.name}_auto_extend",
        lock=ttl_lock,
    ):
        assert await ttl_lock.locked()
        assert await ttl_lock.owned()
        await asyncio.sleep(5 * lock_timeout.total_seconds())
        assert await ttl_lock.locked()
        assert await ttl_lock.owned()
