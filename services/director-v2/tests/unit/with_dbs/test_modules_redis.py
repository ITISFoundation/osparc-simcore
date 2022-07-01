# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

import asyncio
from argparse import Namespace
from asyncio import CancelledError, Task
from contextlib import suppress
from typing import AsyncIterable, Optional

import pytest
from asgi_lifespan import LifespanManager
from faker import Faker
from fastapi import FastAPI
from redis.asyncio import Redis
from redis.asyncio.lock import Lock
from redis.exceptions import LockError
from settings_library.redis import RedisSettings
from simcore_service_director_v2.modules import redis
from simcore_service_director_v2.modules.redis import (
    EXTEND_TASK_ATTR_NAME,
    DockerNodeId,
    RedisLockManager,
    auto_release,
)

pytest_simcore_core_services_selection = [
    "redis",
]

# UTILS


class MockLocksPerNodeProvider:
    def __init__(self, lock_per_node: int) -> None:
        self.lock_per_node = lock_per_node

    async def get(self, *args, **kwargs):
        return self.lock_per_node


# FIXTURES


@pytest.fixture
async def minimal_app(redis_settings: RedisSettings) -> AsyncIterable[FastAPI]:
    app = FastAPI()

    # add expected redis_settings
    app.state.settings = Namespace()
    app.state.settings.REDIS = redis_settings

    # setup redis module
    redis.setup(app)

    async with LifespanManager(app):
        yield app


@pytest.fixture
async def redis_lock_manager(minimal_app: FastAPI) -> AsyncIterable[RedisLockManager]:
    redis_lock_manger = RedisLockManager.instance(minimal_app)
    await redis_lock_manger.redis.flushall()
    yield redis_lock_manger
    await redis_lock_manger.redis.flushall()


@pytest.fixture
def docker_node_id(faker: Faker) -> str:
    return faker.uuid4()


# TESTS


async def test_lock_working_as_expected(
    redis_lock_manager: RedisLockManager, docker_node_id
) -> None:
    lock = redis_lock_manager.redis.lock(docker_node_id)

    lock_acquired = await lock.acquire(blocking=False)
    assert lock_acquired
    assert await lock.locked() is True

    await lock.release()
    assert await lock.locked() is False

    with pytest.raises(LockError):
        await lock.release()


async def test_two_lock_instances(
    redis_lock_manager: RedisLockManager, docker_node_id
) -> None:
    # NOTE: this test show cases how the locks work
    # you have to acquire the lock from the same istance
    # in order to avoid tricky situations

    lock = redis_lock_manager.redis.lock(docker_node_id)

    lock_acquired = await lock.acquire(blocking=False)
    assert lock_acquired
    assert await lock.locked() is True

    # we get a different instance
    second_lock = redis_lock_manager.redis.lock(docker_node_id)
    assert await second_lock.locked() is True

    # cannot release lock form different instance!
    with pytest.raises(LockError):
        await second_lock.release()

    assert await lock.locked() is True
    # NOTE: this is confusing! One woudl expect the second lock to be unlocked
    # but it actually is True
    assert await second_lock.locked() is True

    await lock.release()
    assert await lock.locked() is False
    # NOTE: apparently it mirrors the first lock instance!
    assert await second_lock.locked() is False


async def test_auto_release_ok(
    redis_lock_manager: RedisLockManager, docker_node_id: DockerNodeId
) -> None:
    lock: Optional[Lock] = await redis_lock_manager.acquire_lock(docker_node_id)
    assert lock is not None
    assert await lock.locked() is True

    # code completes without error
    async with auto_release(redis_lock_manager, lock):
        assert await lock.locked() is True

    assert await lock.locked() is False

    # lock was already released and cannot be released again
    with pytest.raises(LockError):
        await redis_lock_manager.release_lock(lock)


async def test_auto_release_on_error_releases_lock(
    redis_lock_manager: RedisLockManager, docker_node_id: DockerNodeId
) -> None:
    lock: Optional[Lock] = await redis_lock_manager.acquire_lock(docker_node_id)
    assert lock is not None
    assert await lock.locked() is True

    # code will raise an error
    with pytest.raises(RuntimeError):
        async with auto_release(redis_lock_manager, lock):
            assert await lock.locked() is True
            raise RuntimeError("Unexpected oops!")

    assert await lock.locked() is False

    # lock was already released and cannot be released again
    with pytest.raises(LockError):
        await redis_lock_manager.release_lock(lock)


@pytest.mark.parametrize("extra_attribute", [EXTEND_TASK_ATTR_NAME])
async def test_no_lock_instance_attribute_collision(
    redis_settings: RedisSettings, extra_attribute: str
) -> None:
    async with Redis.from_url(redis_settings.dsn_locks) as redis:
        lock = Lock(redis=redis, name="test_lock")

        # check no collision occurs with existing defined names
        method_and_attribute_names = dir(lock)
        assert extra_attribute not in method_and_attribute_names

        # set the attribute
        setattr(lock, extra_attribute, None)


async def test_lock_extend_task_life_cycle(
    redis_lock_manager: RedisLockManager, docker_node_id: DockerNodeId
) -> None:
    lock: Optional[Lock] = await redis_lock_manager.acquire_lock(docker_node_id)
    assert lock is not None
    assert await lock.locked() is True

    # task is running and not cancelled
    task: Task = getattr(lock, EXTEND_TASK_ATTR_NAME)
    assert task
    assert task.done() is False
    assert task.cancelled() is False

    await redis_lock_manager.release_lock(lock)

    # task was cancelled and removed
    assert task.done() is True
    assert task.cancelled() is True
    assert getattr(lock, EXTEND_TASK_ATTR_NAME) is None

    # try to cancel again
    with pytest.raises(LockError):
        await redis_lock_manager.release_lock(lock)


@pytest.mark.parametrize("repeat", [2, 10])
@pytest.mark.parametrize("locks_per_node", [4, 10, 100])
async def test_acquire_all_available_node_locks_stress_test(
    redis_lock_manager: RedisLockManager,
    docker_node_id: DockerNodeId,
    repeat: int,
    locks_per_node: int,
) -> None:
    # NOTE: this test is designed to spot if there are any issues when
    # acquiring and releasing locks in parallel with high concurrency

    # adds more stress with lower lock_timeout
    redis_lock_manager.lock_timeout = 1.0

    redis_lock_manager.lock_per_node_provider = MockLocksPerNodeProvider(  # type:ignore
        locks_per_node
    )

    # pylint: disable=protected-access
    total_node_slots = await redis_lock_manager.get_node_slots(docker_node_id)
    assert total_node_slots == locks_per_node

    async def _acquire_lock() -> Lock:
        lock = await redis_lock_manager.acquire_lock(docker_node_id)
        assert lock is not None
        return lock

    async def _release_lock(lock: Lock) -> None:
        async with auto_release(redis_lock_manager, lock):
            assert await lock.locked() is True
        assert await lock.locked() is False

    for _ in range(repeat):
        # acquire locks in parallel
        acquired_locks: tuple[Lock] = await asyncio.gather(
            *[_acquire_lock() for _ in range(total_node_slots)]
        )

        # trying to sleep enough to trigger the next steps while
        # the locks are being refreshed. They are usually refreshed
        # at `redis_lock_manager.lock_timeout * 0.5` interval
        await asyncio.sleep(redis_lock_manager.lock_timeout * 0.48)

        # no more slots are available to acquire any other locks
        with pytest.raises(AssertionError):
            await _acquire_lock()

        # release locks in parallel
        await asyncio.gather(*[_release_lock(lock) for lock in acquired_locks])


async def test_lock_extension_expiration(
    redis_lock_manager: RedisLockManager, docker_node_id: DockerNodeId
) -> None:
    SHORT_INTERVAL = 0.10

    redis_lock_manager.lock_timeout = SHORT_INTERVAL
    redis_lock_manager.lock_per_node_provider = MockLocksPerNodeProvider(  # type:ignore
        1
    )

    lock = await redis_lock_manager.acquire_lock(docker_node_id)
    assert lock is not None

    # lock should have been extended at least 2 times
    # and should still be locked
    await asyncio.sleep(SHORT_INTERVAL * 4)
    assert await lock.locked() is True

    # emulating process died (equivalent to no further renews)
    task: Optional[Task] = getattr(lock, EXTEND_TASK_ATTR_NAME)
    assert task
    task.cancel()
    with suppress(CancelledError):
        await task

    # lock is expected to be unlocked after timeout interval
    await asyncio.sleep(redis_lock_manager.lock_timeout)
    assert await lock.locked() is False
