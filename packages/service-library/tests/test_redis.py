# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=protected-access


import asyncio
import datetime
from typing import AsyncIterator, Callable

import docker
import pytest
from faker import Faker
from redis.exceptions import LockError, LockNotOwnedError
from servicelib.redis import AlreadyLockedError, RedisClientSDK
from settings_library.redis import RedisSettings

pytest_simcore_core_services_selection = [
    "redis",
]

pytest_simcore_ops_services_selection = [
    "redis-commander",
]


async def test_redis_client(redis_service: RedisSettings):
    client = RedisClientSDK(redis_service.dsn_resources)
    assert client
    assert client.redis_dsn == redis_service.dsn_resources
    # check it is correctly initialized
    assert await client.ping() is True
    await client.close()


@pytest.fixture
async def redis_client(
    redis_service: RedisSettings,
) -> AsyncIterator[Callable[[], RedisClientSDK]]:
    created_clients = []

    def _creator() -> RedisClientSDK:
        client = RedisClientSDK(redis_service.dsn_resources)
        assert client
        created_clients.append(client)
        return client

    yield _creator
    # cleanup, properly close the clients
    await asyncio.gather(
        *(client.redis.flushall() for client in created_clients), return_exceptions=True
    )
    await asyncio.gather(*(client.close() for client in created_clients))


@pytest.fixture
def lock_timeout() -> datetime.timedelta:
    return datetime.timedelta(seconds=1)


async def test_redis_key_encode_decode(
    redis_client: Callable[[], RedisClientSDK],
    faker: Faker,
):
    client = redis_client()
    key = faker.pystr()
    value = faker.pystr()
    await client.redis.set(key, value)
    val = await client.redis.get(key)
    assert val == value
    await client.redis.delete(key)


async def test_redis_lock_acquisition(
    redis_client: Callable[[], RedisClientSDK], faker: Faker
):
    client = redis_client()

    lock_name = faker.pystr()
    lock = client.redis.lock(lock_name)
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
    same_lock = client.redis.lock(lock_name)
    assert await same_lock.locked() is True
    assert await same_lock.owned() is False
    assert await same_lock.acquire(blocking=False) is False

    # now release the lock
    await lock.release()
    assert not await lock.locked()
    assert not await lock.owned()


async def test_redis_lock_context_manager(
    redis_client: Callable[[], RedisClientSDK], faker: Faker
):
    client = redis_client()
    lock_name = faker.pystr()
    lock = client.redis.lock(lock_name)
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
        same_lock = client.redis.lock(lock_name, blocking_timeout=1)
        assert await same_lock.locked()
        assert not await same_lock.owned()
        assert await same_lock.acquire() == False
        with pytest.raises(LockError):
            async with same_lock:
                ...
    assert not await lock.locked()


async def test_redis_lock_with_ttl(
    redis_client: Callable[[], RedisClientSDK],
    faker: Faker,
    lock_timeout: datetime.timedelta,
):
    client = redis_client()
    ttl_lock = client.redis.lock(faker.pystr(), timeout=lock_timeout.total_seconds())
    assert not await ttl_lock.locked()

    with pytest.raises(LockNotOwnedError):
        # this raises as the lock is lost
        async with ttl_lock:
            assert await ttl_lock.locked()
            assert await ttl_lock.owned()
            await asyncio.sleep(2 * lock_timeout.total_seconds())
            assert not await ttl_lock.locked()


async def test_lock_context(
    redis_client: Callable[[], RedisClientSDK],
    faker: Faker,
    lock_timeout: datetime.timedelta,
):
    client = redis_client()
    lock_name = faker.pystr()
    assert await client.is_locked(lock_name) is False
    async with client.lock_context(lock_name) as ttl_lock:
        assert await client.is_locked(lock_name) is True
        assert await ttl_lock.owned() is True
        await asyncio.sleep(5 * lock_timeout.total_seconds())
        assert await client.is_locked(lock_name) is True
        assert await ttl_lock.owned() is True
    assert await client.is_locked(lock_name) is False
    assert await ttl_lock.owned() is False


async def test_lock_context_with_already_locked_lock_raises(
    redis_client: Callable[[], RedisClientSDK],
    faker: Faker,
):
    client = redis_client()
    lock_name = faker.pystr()
    assert await client.is_locked(lock_name) is False
    async with client.lock_context(lock_name) as lock:
        assert await client.is_locked(lock_name) is True

        with pytest.raises(AlreadyLockedError):
            assert isinstance(lock.name, str)
            async with client.lock_context(lock.name):
                ...
        assert await lock.locked() is True
    assert await client.is_locked(lock_name) is False


async def test_lock_context_with_data(
    redis_client: Callable[[], RedisClientSDK], faker: Faker
):
    client = redis_client()
    lock_data = faker.text()
    lock_name = faker.pystr()
    assert await client.is_locked(lock_name) is False
    assert await client.lock_value(lock_name) is None
    async with client.lock_context(lock_name, lock_value=lock_data) as lock:
        assert await client.is_locked(lock_name) is True
        assert await client.lock_value(lock_name) == lock_data
    assert await client.is_locked(lock_name) is False
    assert await client.lock_value(lock_name) is None


async def test_redis_client_lose_connection(
    redis_client: Callable[[], RedisClientSDK],
    docker_client: docker.client.DockerClient,
):
    client = redis_client()
    assert await client.ping() is True
    # now let's put down the rabbit service
    for rabbit_docker_service in (
        docker_service
        for docker_service in docker_client.services.list()
        if "redis" in docker_service.name  # type: ignore
    ):
        rabbit_docker_service.remove()  # type: ignore
    await asyncio.sleep(10)  # wait for the client to disconnect
    assert await client.ping() is False
