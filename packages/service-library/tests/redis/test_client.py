# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=protected-access


import asyncio
import datetime
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager

import pytest
from redis.exceptions import LockError, LockNotOwnedError
from servicelib.redis import RedisClientSDK
from settings_library.redis import RedisDatabase, RedisSettings
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_delay,
    wait_fixed,
)

pytest_simcore_core_services_selection = [
    "redis",
]

pytest_simcore_ops_services_selection = [
    "redis-commander",
]


@pytest.fixture
def redis_lock_ttl() -> datetime.timedelta:
    return datetime.timedelta(seconds=1)


async def test_redis_lock_no_ttl(redis_client_sdk: RedisClientSDK, lock_name: str):
    lock = redis_client_sdk.create_lock(lock_name, ttl=None)
    assert await lock.locked() is False

    lock_acquired = await lock.acquire(blocking=False)
    assert lock_acquired is True
    assert await lock.locked() is True
    assert await lock.owned() is True
    with pytest.raises(LockError):
        # a lock with no ttl cannot be reacquired
        await lock.reacquire()
    with pytest.raises(LockError):
        # a lock with no ttl cannot be extended
        await lock.extend(2)

    # try to acquire the lock a second time
    same_lock = redis_client_sdk.create_lock(lock_name, ttl=None)
    assert await same_lock.locked() is True
    assert await same_lock.owned() is False
    assert await same_lock.acquire(blocking=False) is False

    # now release the lock
    await lock.release()
    assert not await lock.locked()
    assert not await lock.owned()


async def test_redis_lock_context_manager_no_ttl(
    redis_client_sdk: RedisClientSDK, lock_name: str
):
    lock = redis_client_sdk.create_lock(lock_name, ttl=None)
    assert not await lock.locked()

    async with lock:
        assert await lock.locked()
        assert await lock.owned()
        with pytest.raises(LockError):
            # a lock with no timeout cannot be reacquired
            await lock.reacquire()

        with pytest.raises(LockError):
            # a lock with no timeout cannot be extended
            await lock.extend(2)

        # try to acquire the lock a second time
        same_lock = redis_client_sdk.create_lock(lock_name, ttl=None)
        assert await same_lock.locked()
        assert not await same_lock.owned()
        assert await same_lock.acquire() is False
        with pytest.raises(LockError):
            async with same_lock:
                ...
    assert not await lock.locked()


async def test_redis_lock_with_ttl(
    redis_client_sdk: RedisClientSDK, lock_name: str, redis_lock_ttl: datetime.timedelta
):
    ttl_lock = redis_client_sdk.create_lock(lock_name, ttl=redis_lock_ttl)
    assert not await ttl_lock.locked()

    with pytest.raises(LockNotOwnedError):  # noqa: PT012
        # this raises as the lock is lost
        async with ttl_lock:
            assert await ttl_lock.locked()
            assert await ttl_lock.owned()
            await asyncio.sleep(2 * redis_lock_ttl.total_seconds())
            assert not await ttl_lock.locked()


async def test_redis_client_sdk_setup_shutdown(
    mock_redis_socket_timeout: None, redis_service: RedisSettings
):
    # setup
    redis_resources_dns = redis_service.build_redis_dsn(RedisDatabase.RESOURCES)
    client = RedisClientSDK(redis_resources_dns, client_name="pytest")
    assert client
    assert client.redis_dsn == redis_resources_dns

    # ensure health check task sets the health to True
    client._is_healthy = False  # noqa: SLF001

    await client.setup()
    async for attempt in AsyncRetrying(
        wait=wait_fixed(0.1),
        stop=stop_after_delay(10),
        reraise=True,
        retry=retry_if_exception_type(AssertionError),
    ):
        with attempt:
            assert client.is_healthy is True

    # cleanup
    await client.redis.flushall()
    await client.shutdown()


async def test_regression_fails_on_redis_service_outage(
    mock_redis_socket_timeout: None,
    paused_container: Callable[[str], AbstractAsyncContextManager[None]],
    redis_client_sdk: RedisClientSDK,
):
    assert await redis_client_sdk.ping() is True

    async with paused_container("redis"):
        # no connection available any longer should not hang but timeout
        assert await redis_client_sdk.ping() is False

    assert await redis_client_sdk.ping() is True
