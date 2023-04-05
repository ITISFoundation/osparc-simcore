# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=protected-access


import asyncio
import datetime
from typing import AsyncIterator, Final

import docker
import pytest
from faker import Faker
from pytest_mock import MockerFixture
from redis.exceptions import LockError, LockNotOwnedError
from servicelib import redis as servicelib_redis
from servicelib.redis import (
    CouldNotAcquireLockError,
    RedisClientSDK,
    RedisClientsManager,
    _get_lock_renew_interval,
)
from settings_library.redis import RedisDatabase, RedisSettings
from tenacity._asyncio import AsyncRetrying
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_fixed

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
    redis_service: RedisSettings,
) -> AsyncIterator[RedisClientSDK]:
    redis_resources_dns = redis_service.build_redis_dsn(RedisDatabase.RESOURCES)
    client = RedisClientSDK(redis_resources_dns)
    assert client
    assert client.redis_dsn == redis_resources_dns
    await client.setup()

    yield client
    # cleanup, properly close the clients
    await client.redis.flushall()
    await client.shutdown()


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
        assert await same_lock.acquire() == False
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

    with pytest.raises(LockNotOwnedError):
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

        with pytest.raises(CouldNotAcquireLockError):
            assert isinstance(lock.name, str)
            async with redis_client_sdk.lock_context(lock.name):
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


async def test_lock_acquired_in_parallel_to_update_same_resource(
    mock_default_lock_ttl: None, redis_client_sdk: RedisClientSDK, faker: Faker
):
    INCREASE_OPERATIONS: Final[int] = 50
    INCREASE_BY: Final[int] = 10

    class RaceConditionCounter:
        def __init__(self):
            self.value: int = 0

        async def race_condition_increase(self, by: int) -> None:
            current_value = self.value
            current_value += by
            # most likely situation which creates issues
            await asyncio.sleep(_get_lock_renew_interval().total_seconds())
            self.value = current_value

    counter = RaceConditionCounter()
    lock_name: str = faker.pystr()
    time_for_all_inc_counter_calls_to_finish_s: float = (
        servicelib_redis._DEFAULT_LOCK_TTL.total_seconds() * INCREASE_OPERATIONS * 10
    )

    async def _inc_counter() -> None:
        async with redis_client_sdk.lock_context(
            lock_key=lock_name,
            blocking=True,
            blocking_timeout_s=time_for_all_inc_counter_calls_to_finish_s,
        ):
            await counter.race_condition_increase(INCREASE_BY)

    await asyncio.gather(*(_inc_counter() for _ in range(INCREASE_OPERATIONS)))
    assert counter.value == INCREASE_BY * INCREASE_OPERATIONS


async def test_redis_client_sdks_manager(redis_service: RedisSettings):
    all_redis_databases: set[int] = set(RedisDatabase)
    manager = RedisClientsManager(databases=all_redis_databases, settings=redis_service)

    await manager.setup()

    for database in all_redis_databases:
        assert manager.client(database)

    await manager.shutdown()


# NOTE: keep this test last as it breaks the service `redis`
# from `pytest_simcore_core_services_selection`
# since the service is being removed
async def test_redis_client_sdk_lost_connection(
    redis_service: RedisSettings, docker_client: docker.client.DockerClient
):
    redis_client_sdk = RedisClientSDK(
        redis_service.build_redis_dsn(RedisDatabase.RESOURCES)
    )

    await redis_client_sdk.setup()

    assert await redis_client_sdk.ping() is True
    # now let's put down the rabbit service
    for rabbit_docker_service in (
        docker_service
        for docker_service in docker_client.services.list()
        if "redis" in docker_service.name  # type: ignore
    ):
        rabbit_docker_service.remove()  # type: ignore

    # check that connection was lost
    async for attempt in AsyncRetrying(
        stop=stop_after_delay(60), wait=wait_fixed(0.5), reraise=True
    ):
        with attempt:
            assert await redis_client_sdk.ping() is False
