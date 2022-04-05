# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import asyncio

import pytest
import redis
import redis.asyncio as aioredis


async def test_aioredis(redis_client: aioredis.Redis):
    await redis_client.set("my-key", "value")
    val = await redis_client.get("my-key")
    assert val == "value"


async def test_redlocks_features(redis_client: aioredis.Redis):
    # Check wether a resourece acquired by any other redlock instance:
    lock = redis_client.lock("resource_name")
    assert not await lock.locked()

    # Try to acquire the lock:
    lock_acquired = await lock.acquire(blocking=False)
    assert lock_acquired, "Lock not acquired"
    await lock.release()
    assert not await lock.locked()
    assert not await lock.owned()

    # use as context manager
    async with lock:
        assert await lock.locked()
        assert await lock.owned()
        # a lock with no timeout cannot be extended
        with pytest.raises(redis.exceptions.LockError):
            await lock.extend(2)
        # try to acquire the lock a second time
        same_lock = redis_client.lock("resource_name", blocking_timeout=1)
        assert await same_lock.locked()
        assert not await same_lock.owned()
        assert await same_lock.acquire() == False
        with pytest.raises(redis.exceptions.LockError):
            async with same_lock:
                ...
    assert not await lock.locked()

    # now create a lock with a ttl
    ttl_lock = redis_client.lock("ttl_resource", timeout=2, blocking_timeout=1)
    assert not await ttl_lock.locked()
    with pytest.raises(redis.exceptions.LockNotOwnedError):
        # this raises as the lock is lost
        async with ttl_lock:
            assert await ttl_lock.locked()
            assert await ttl_lock.owned()
            await asyncio.sleep(3)
            assert not await ttl_lock.locked()
