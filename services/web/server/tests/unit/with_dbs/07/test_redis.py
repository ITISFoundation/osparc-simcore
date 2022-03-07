# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import pytest
from aioredis import Redis
from aioredlock import Aioredlock, LockError
from yarl import URL


@pytest.fixture
async def lock_manager(redis_service: URL):
    lm = Aioredlock(
        [
            str(redis_service),
        ]
    )

    yield lm

    # Clear the connections with Redis:
    await lm.destroy()


async def test_redlocks_features(lock_manager: Aioredlock):
    # Originally https://github.com/joanvila/aioredlock#readme

    # Check wether a resourece acquired by any other redlock instance:
    assert not await lock_manager.is_locked("resource_name")

    # Try to acquire the lock:
    try:
        lock = await lock_manager.lock("resource_name", lock_timeout=10)
    except LockError:
        print("Lock not acquired")
        raise

    # Now the lock is acquired:
    assert lock.valid
    assert await lock_manager.is_locked("resource_name")

    # Extend lifetime of the lock:
    await lock_manager.extend(lock, lock_timeout=10)
    # Raises LockError if the lock manager can not extend the lock lifetime
    # on more then half of the Redis instances.

    # Release the lock:
    await lock_manager.unlock(lock)
    # Raises LockError if the lock manager can not release the lock
    # on more then half of redis instances.

    # The released lock become invalid:
    assert not lock.valid
    assert not await lock_manager.is_locked("resource_name")

    # Or you can use the lock as async context manager:
    try:
        async with await lock_manager.lock("resource_name") as lock:
            assert lock.valid is True
            # Do your stuff having the lock
            await lock.extend()  # alias for lock_manager.extend(lock)
            # Do more stuff having the lock
        assert lock.valid is False  # lock will be released by context manager
    except LockError:
        print("Lock not acquired")
        raise

    await lock_manager.destroy()


async def test_aioredis(redis_client: Redis):
    await redis_client.set("my-key", "value")
    val = await redis_client.get("my-key")
    assert val == "value"
