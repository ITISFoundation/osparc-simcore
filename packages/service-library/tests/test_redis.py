# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=protected-access


import asyncio
import datetime
from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager
from typing import Final

import pytest
from faker import Faker
from pytest_mock import MockerFixture
from redis.exceptions import LockError, LockNotOwnedError
from servicelib import redis as servicelib_redis
from servicelib.redis import (
    CouldNotAcquireLockError,
    RedisClientSDK,
    RedisClientsManager,
    RedisManagerDBConfig,
)
from servicelib.utils import limited_gather
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
    # "redis-commander",
]


async def _is_locked(redis_client_sdk: RedisClientSDK, lock_name: str) -> bool:
    lock = redis_client_sdk.redis.lock(lock_name)
    return await lock.locked()


@pytest.fixture
async def redis_client_sdk(
    get_redis_client_sdk: Callable[
        [RedisDatabase], AbstractAsyncContextManager[RedisClientSDK]
    ]
) -> AsyncIterator[RedisClientSDK]:
    async with get_redis_client_sdk(RedisDatabase.RESOURCES) as client:
        yield client


@pytest.fixture
def lock_timeout() -> datetime.timedelta:
    return datetime.timedelta(seconds=1)


@pytest.fixture
def mock_default_lock_ttl(mocker: MockerFixture) -> None:
    mocker.patch.object(
        servicelib_redis, "_DEFAULT_LOCK_TTL", datetime.timedelta(seconds=0.25)
    )


async def test_redis_key_encode_decode(redis_client_sdk: RedisClientSDK, faker: Faker):
    key = faker.pystr()
    value = faker.pystr()
    await redis_client_sdk.redis.set(key, value)
    val = await redis_client_sdk.redis.get(key)
    assert val == value
    await redis_client_sdk.redis.delete(key)


async def test_redis_lock_acquisition(redis_client_sdk: RedisClientSDK, faker: Faker):
    lock_name = faker.pystr()
    lock = redis_client_sdk.redis.lock(lock_name)
    assert await lock.locked() is False

    # Try to acquire the lock:
    lock_acquired = await lock.acquire(blocking=False)
    assert lock_acquired is True
    assert await lock.locked() is True
    assert await lock.owned() is True
    with pytest.raises(LockError):
        # a lock with no timeout cannot be reacquired
        await lock.reacquire()
    with pytest.raises(LockError):
        # a lock with no timeout cannot be extended
        await lock.extend(2)

    # try to acquire the lock a second time
    same_lock = redis_client_sdk.redis.lock(lock_name)
    assert await same_lock.locked() is True
    assert await same_lock.owned() is False
    assert await same_lock.acquire(blocking=False) is False

    # now release the lock
    await lock.release()
    assert not await lock.locked()
    assert not await lock.owned()


async def test_redis_lock_context_manager(
    redis_client_sdk: RedisClientSDK, faker: Faker
):
    lock_name = faker.pystr()
    lock = redis_client_sdk.redis.lock(lock_name)
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
        same_lock = redis_client_sdk.redis.lock(lock_name, blocking_timeout=1)
        assert await same_lock.locked()
        assert not await same_lock.owned()
        assert await same_lock.acquire() is False
        with pytest.raises(LockError):
            async with same_lock:
                ...
    assert not await lock.locked()


async def test_redis_lock_with_ttl(
    redis_client_sdk: RedisClientSDK, faker: Faker, lock_timeout: datetime.timedelta
):
    ttl_lock = redis_client_sdk.redis.lock(
        faker.pystr(), timeout=lock_timeout.total_seconds()
    )
    assert not await ttl_lock.locked()

    with pytest.raises(LockNotOwnedError):  # noqa: PT012
        # this raises as the lock is lost
        async with ttl_lock:
            assert await ttl_lock.locked()
            assert await ttl_lock.owned()
            await asyncio.sleep(2 * lock_timeout.total_seconds())
            assert not await ttl_lock.locked()


async def test_lock_context(
    redis_client_sdk: RedisClientSDK, faker: Faker, lock_timeout: datetime.timedelta
):
    lock_name = faker.pystr()
    assert await _is_locked(redis_client_sdk, lock_name) is False
    async with redis_client_sdk.lock_context(lock_name) as ttl_lock:
        assert await _is_locked(redis_client_sdk, lock_name) is True
        assert await ttl_lock.owned() is True
        await asyncio.sleep(5 * lock_timeout.total_seconds())
        assert await _is_locked(redis_client_sdk, lock_name) is True
        assert await ttl_lock.owned() is True
    assert await _is_locked(redis_client_sdk, lock_name) is False
    assert await ttl_lock.owned() is False


async def test_lock_context_with_already_locked_lock_raises(
    redis_client_sdk: RedisClientSDK, faker: Faker
):
    lock_name = faker.pystr()
    assert await _is_locked(redis_client_sdk, lock_name) is False
    async with redis_client_sdk.lock_context(lock_name) as lock:
        assert await _is_locked(redis_client_sdk, lock_name) is True

        assert isinstance(lock.name, str)

        # case where gives up immediately to acquire lock without waiting
        with pytest.raises(CouldNotAcquireLockError):
            async with redis_client_sdk.lock_context(lock.name, blocking=False):
                ...

        # case when lock waits up to blocking_timeout_s before giving up on
        # lock acquisition
        with pytest.raises(CouldNotAcquireLockError):
            async with redis_client_sdk.lock_context(
                lock.name, blocking=True, blocking_timeout_s=0.1
            ):
                ...

        assert await lock.locked() is True
    assert await _is_locked(redis_client_sdk, lock_name) is False


async def test_lock_context_with_data(redis_client_sdk: RedisClientSDK, faker: Faker):
    lock_data = faker.text()
    lock_name = faker.pystr()
    assert await _is_locked(redis_client_sdk, lock_name) is False
    assert await redis_client_sdk.lock_value(lock_name) is None
    async with redis_client_sdk.lock_context(lock_name, lock_value=lock_data) as lock:
        assert await _is_locked(redis_client_sdk, lock_name) is True
        assert await redis_client_sdk.lock_value(lock_name) == lock_data
    assert await _is_locked(redis_client_sdk, lock_name) is False
    assert await redis_client_sdk.lock_value(lock_name) is None


async def test_lock_context_released_after_error(
    redis_client_sdk: RedisClientSDK, faker: Faker
):
    lock_name = faker.pystr()

    assert await redis_client_sdk.lock_value(lock_name) is None

    with pytest.raises(RuntimeError):  # noqa: PT012
        async with redis_client_sdk.lock_context(lock_name):
            assert await redis_client_sdk.redis.get(lock_name) is not None
            msg = "Expected error"
            raise RuntimeError(msg)

    assert await redis_client_sdk.lock_value(lock_name) is None


async def test_lock_acquired_in_parallel_to_update_same_resource(
    mock_default_lock_ttl: None,
    get_redis_client_sdk: Callable[
        [RedisDatabase], AbstractAsyncContextManager[RedisClientSDK]
    ],
    faker: Faker,
):
    INCREASE_OPERATIONS: Final[int] = 250
    INCREASE_BY: Final[int] = 10

    class RaceConditionCounter:
        def __init__(self):
            self.value: int = 0

        async def race_condition_increase(self, by: int) -> None:
            current_value = self.value
            current_value += by
            # most likely situation which creates issues
            await asyncio.sleep(
                servicelib_redis._DEFAULT_LOCK_TTL.total_seconds() / 2  # noqa: SLF001
            )
            self.value = current_value

    counter = RaceConditionCounter()
    lock_name: str = faker.pystr()
    # ensures it does nto time out before acquiring the lock
    time_for_all_inc_counter_calls_to_finish_s: float = (
        servicelib_redis._DEFAULT_LOCK_TTL.total_seconds()  # noqa: SLF001
        * INCREASE_OPERATIONS
        * 10
    )

    async def _inc_counter() -> None:
        async with get_redis_client_sdk(  # noqa: SIM117
            RedisDatabase.RESOURCES
        ) as redis_client_sdk:
            async with redis_client_sdk.lock_context(
                lock_key=lock_name,
                blocking=True,
                blocking_timeout_s=time_for_all_inc_counter_calls_to_finish_s,
            ):
                await counter.race_condition_increase(INCREASE_BY)

    await limited_gather(
        *(_inc_counter() for _ in range(INCREASE_OPERATIONS)), limit=15
    )
    assert counter.value == INCREASE_BY * INCREASE_OPERATIONS


async def test_redis_client_sdks_manager(
    mock_redis_socket_timeout: None, redis_service: RedisSettings
):

    all_redis_configs: set[RedisManagerDBConfig] = {
        RedisManagerDBConfig(db) for db in RedisDatabase
    }
    manager = RedisClientsManager(
        databases_configs=all_redis_configs,
        settings=redis_service,
        client_name="pytest",
    )

    async with manager:
        for config in all_redis_configs:
            assert manager.client(config.database)


async def test_redis_client_sdk_setup_shutdown(
    mock_redis_socket_timeout: None, redis_service: RedisSettings
):
    # setup
    redis_resources_dns = redis_service.build_redis_dsn(RedisDatabase.RESOURCES)
    client = RedisClientSDK(redis_resources_dns, client_name="pytest")
    assert client
    assert client.redis_dsn == redis_resources_dns

    # ensure nothing happens if shutdown is called before setup
    await client.shutdown()

    await client.setup()

    # ensure health check task sets the health to True
    client._is_healthy = False  # noqa: SLF001
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


@pytest.fixture
def mock_default_socket_timeout(mocker: MockerFixture) -> None:
    mocker.patch.object(
        servicelib_redis, "_DEFAULT_SOCKET_TIMEOUT", datetime.timedelta(seconds=0.25)
    )


async def test_regression_fails_on_redis_service_outage(
    mock_default_socket_timeout: None,
    paused_container: Callable[[str], AbstractAsyncContextManager[None]],
    redis_client_sdk: RedisClientSDK,
):
    assert await redis_client_sdk.ping() is True

    async with paused_container("redis"):
        # no connection available any longer should not hang but timeout
        assert await redis_client_sdk.ping() is False

    assert await redis_client_sdk.ping() is True
