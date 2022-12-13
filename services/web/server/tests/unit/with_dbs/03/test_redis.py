# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import asyncio

import pytest
import redis
import redis.asyncio as aioredis
from faker import Faker


async def test_aioredis(redis_client: aioredis.Redis, faker: Faker):
    key = faker.pystr()
    value = faker.pystr()
    await redis_client.set(key, value)
    val = await redis_client.get(key)
    assert val == value


async def test_lock_acquisition(redis_client: aioredis.Redis, faker: Faker):
    lock = redis_client.lock(faker.pystr())
    assert not await lock.locked()

    # Try to acquire the lock:
    lock_acquired = await lock.acquire(blocking=False)
    assert lock_acquired, "Lock not acquired"
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
        # a lock with no timeout cannot be extended
        with pytest.raises(redis.exceptions.LockError):
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


async def test_lock_with_ttl(redis_client: aioredis.Redis, faker: Faker):
    ttl_lock = redis_client.lock(faker.pystr(), timeout=2, blocking_timeout=1)
    assert not await ttl_lock.locked()

    with pytest.raises(redis.exceptions.LockNotOwnedError):
        # this raises as the lock is lost
        async with ttl_lock:
            assert await ttl_lock.locked()
            assert await ttl_lock.owned()
            await asyncio.sleep(3)
            assert not await ttl_lock.locked()
