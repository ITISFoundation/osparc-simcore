# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=protected-access

import asyncio
from argparse import Namespace
from asyncio import CancelledError, Task
from contextlib import suppress
from typing import AsyncIterable, Callable, Optional

import pytest
from asgi_lifespan import LifespanManager
from faker import Faker
from fastapi import FastAPI
from redis.exceptions import LockError
from settings_library.redis import RedisSettings
from pytest_mock import MockerFixture
from simcore_service_director_v2.modules import redis
from simcore_service_director_v2.modules.redis import (
    ExtendLock,
    DockerNodeId,
    RedisLockManager,
    auto_release,
)

pytest_simcore_core_services_selection = [
    "redis",
]


# FIXTURES


@pytest.fixture
def mock_default_locks_per_node(mocker: MockerFixture) -> Callable[[int], None]:
    def mock_default(slots: int) -> None:
        mocker.patch(
            "simcore_service_director_v2.modules.redis.DEFAULT_LOCKS_PER_NODE", slots
        )

    return mock_default


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
    await redis_lock_manger._redis.flushall()
    yield redis_lock_manger
    await redis_lock_manger._redis.flushall()


@pytest.fixture
def docker_node_id(faker: Faker) -> str:
    return faker.uuid4()


# TESTS


async def test_redis_lock_working_as_expected(
    redis_lock_manager: RedisLockManager, docker_node_id
) -> None:
    lock = redis_lock_manager._redis.lock(docker_node_id)

    lock_acquired = await lock.acquire(blocking=False)
    assert lock_acquired
    assert await lock.locked() is True

    await lock.release()
    assert await lock.locked() is False

    with pytest.raises(LockError):
        await lock.release()


async def test_redis_two_lock_instances(
    redis_lock_manager: RedisLockManager, docker_node_id: DockerNodeId
) -> None:
    # NOTE: this test show cases how the locks work
    # you have to acquire the lock from the same istance
    # in order to avoid tricky situations

    lock = redis_lock_manager._redis.lock(docker_node_id)

    lock_acquired = await lock.acquire(blocking=False)
    assert lock_acquired
    assert await lock.locked() is True

    # we get a different instance
    second_lock = redis_lock_manager._redis.lock(docker_node_id)
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
    extend_lock: Optional[ExtendLock] = await redis_lock_manager.acquire_lock(
        docker_node_id
    )
    assert extend_lock is not None
    assert await extend_lock._lock.locked() is True

    # code completes without error
    async with auto_release(redis_lock_manager, extend_lock):
        assert await extend_lock._lock.locked() is True

    assert await extend_lock._lock.locked() is False

    # lock was already released and cannot be released again
    with pytest.raises(LockError):
        await redis_lock_manager.release_lock(extend_lock)


async def test_auto_release_on_error_releases_lock(
    redis_lock_manager: RedisLockManager, docker_node_id: DockerNodeId
) -> None:
    lock: Optional[ExtendLock] = await redis_lock_manager.acquire_lock(docker_node_id)
    assert lock is not None
    assert await lock._lock.locked() is True

    # code will raise an error
    with pytest.raises(RuntimeError):
        async with auto_release(redis_lock_manager, lock):
            assert await lock._lock.locked() is True
            raise RuntimeError("Unexpected oops!")

    assert await lock._lock.locked() is False

    # lock was already released and cannot be released again
    with pytest.raises(LockError):
        await redis_lock_manager.release_lock(lock)


async def test_lock_extend_task_life_cycle(
    redis_lock_manager: RedisLockManager, docker_node_id: DockerNodeId
) -> None:
    lock: Optional[ExtendLock] = await redis_lock_manager.acquire_lock(docker_node_id)
    assert lock is not None
    assert await lock._lock.locked() is True

    # task is running and not cancelled
    task: Optional[Task] = lock.task
    assert task
    assert task.done() is False
    assert task.cancelled() is False

    await redis_lock_manager.release_lock(lock)

    # task was cancelled and removed
    assert task.done() is True
    assert task.cancelled() is True
    assert lock.task is None

    # try to cancel again
    with pytest.raises(LockError):
        await redis_lock_manager.release_lock(lock)


@pytest.mark.parametrize("repeat", [2, 10])
@pytest.mark.parametrize("locks_per_node", [4, 10, 100])
async def test_acquire_all_available_node_locks_stress_test(
    redis_lock_manager: RedisLockManager,
    docker_node_id: DockerNodeId,
    repeat: int,
    mock_default_locks_per_node: Callable[[int], None],
    locks_per_node: int,
) -> None:
    # NOTE: this test is designed to spot if there are any issues when
    # acquiring and releasing locks in parallel with high concurrency

    # adds more stress with lower lock_timeout_s
    redis_lock_manager.lock_timeout_s = 1.0

    mock_default_locks_per_node(locks_per_node)

    total_node_slots = await redis_lock_manager._get_node_slots(docker_node_id)
    assert total_node_slots == locks_per_node

    async def _acquire_lock() -> ExtendLock:
        lock = await redis_lock_manager.acquire_lock(docker_node_id)
        assert lock is not None
        return lock

    async def _release_lock(lock: ExtendLock) -> None:
        async with auto_release(redis_lock_manager, lock):
            assert await lock._lock.locked() is True
        assert await lock._lock.locked() is False

    for _ in range(repeat):
        # acquire locks in parallel
        acquired_locks: tuple[ExtendLock] = await asyncio.gather(
            *[_acquire_lock() for _ in range(total_node_slots)]
        )

        # trying to sleep enough to trigger the next steps while
        # the locks are being refreshed. They are usually refreshed
        # at `redis_lock_manager.lock_timeout_s * 0.5` interval
        await asyncio.sleep(redis_lock_manager.lock_timeout_s * 0.48)

        # no more slots are available to acquire any other locks
        with pytest.raises(AssertionError):
            await _acquire_lock()

        # release locks in parallel
        await asyncio.gather(*[_release_lock(lock) for lock in acquired_locks])


async def test_lock_extension_expiration(
    redis_lock_manager: RedisLockManager,
    docker_node_id: DockerNodeId,
    mock_default_locks_per_node: Callable[[int], None],
) -> None:
    SHORT_INTERVAL = 0.10

    redis_lock_manager.lock_timeout_s = SHORT_INTERVAL
    mock_default_locks_per_node(1)

    lock = await redis_lock_manager.acquire_lock(docker_node_id)
    assert lock is not None

    # lock should have been extended at least 2 times
    # and should still be locked
    await asyncio.sleep(SHORT_INTERVAL * 4)
    assert await lock._lock.locked() is True

    # emulating process died (equivalent to no further renews)
    task: Optional[Task] = lock.task
    assert task
    task.cancel()
    with suppress(CancelledError):
        await task

    # lock is expected to be unlocked after timeout interval
    await asyncio.sleep(redis_lock_manager.lock_timeout_s)
    assert await lock._lock.locked() is False
