# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=protected-access

import asyncio
from asyncio import CancelledError
from contextlib import suppress
from typing import Any, AsyncIterable

import pytest
from _pytest.monkeypatch import MonkeyPatch
from asgi_lifespan import LifespanManager
from faker import Faker
from fastapi import FastAPI
from pydantic import PositiveFloat
from redis.exceptions import LockError, LockNotOwnedError
from settings_library.redis import RedisSettings
from simcore_service_director_v2.core.errors import LockAcquireError
from simcore_service_director_v2.core.settings import AppSettings
from simcore_service_director_v2.modules import redis
from simcore_service_director_v2.modules.redis import (
    DockerNodeId,
    ExtendLock,
    SlotsManager,
)

pytest_simcore_core_services_selection = [
    "redis",
]


# UTILS
TEST_RESOURCE = "a_resource"


async def _assert_lock_acquired_and_released(
    slots_manager: SlotsManager,
    docker_node_id: DockerNodeId,
    *,
    sleep_before_release: PositiveFloat,
) -> ExtendLock:
    async with slots_manager.lock(
        docker_node_id, resource_name=TEST_RESOURCE
    ) as extend_lock:
        assert await extend_lock._redis_lock.locked() is True
        assert await extend_lock._redis_lock.owned() is True

        # task is running and not cancelled
        assert extend_lock.task
        assert extend_lock.task.done() is False
        assert extend_lock.task.cancelled() is False

        await asyncio.sleep(sleep_before_release)

    # task was canceled and lock is unlocked and not owned
    assert extend_lock.task is None
    assert await extend_lock._redis_lock.locked() is False
    assert await extend_lock._redis_lock.owned() is False

    return extend_lock


# FIXTURES


@pytest.fixture
async def minimal_app(
    project_env_devel_environment: dict[str, Any],
    redis_settings: RedisSettings,
    monkeypatch: MonkeyPatch,
) -> AsyncIterable[FastAPI]:
    monkeypatch.setenv("REDIS_HOST", redis_settings.REDIS_HOST)
    monkeypatch.setenv("REDIS_PORT", f"{redis_settings.REDIS_PORT}")

    app = FastAPI()

    # add expected redis_settings
    app.state.settings = AppSettings.create_from_envs()

    # setup redis module
    redis.setup(app)

    async with LifespanManager(app):
        yield app


@pytest.fixture
async def slots_manager(minimal_app: FastAPI) -> AsyncIterable[SlotsManager]:
    redis_lock_manger = SlotsManager.instance(minimal_app)
    await redis_lock_manger._redis.flushall()
    yield redis_lock_manger
    await redis_lock_manger._redis.flushall()


@pytest.fixture
def docker_node_id(faker: Faker) -> str:
    return faker.uuid4()


# TESTS


async def test_redis_lock_working_as_expected(
    slots_manager: SlotsManager, docker_node_id
) -> None:
    lock = slots_manager._redis.lock(docker_node_id)

    lock_acquired = await lock.acquire(blocking=False)
    assert lock_acquired
    assert await lock.locked() is True

    await lock.release()
    assert await lock.locked() is False

    with pytest.raises(LockError):
        await lock.release()


async def test_redis_two_lock_instances(
    slots_manager: SlotsManager, docker_node_id: DockerNodeId
) -> None:
    # NOTE: this test show cases how the locks work
    # you have to acquire the lock from the same istance
    # in order to avoid tricky situations

    lock = slots_manager._redis.lock(docker_node_id)

    lock_acquired = await lock.acquire(blocking=False)
    assert lock_acquired
    assert await lock.locked() is True

    # we get a different instance
    second_lock = slots_manager._redis.lock(docker_node_id)
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


async def test_lock_extend_task_life_cycle(
    slots_manager: SlotsManager, docker_node_id: DockerNodeId
) -> None:
    extend_lock = await _assert_lock_acquired_and_released(
        slots_manager, docker_node_id, sleep_before_release=0
    )

    # try to cancel again will not work!
    with pytest.raises(LockError):
        await slots_manager._release_extend_lock(extend_lock)


async def test_no_more_locks_can_be_acquired(
    slots_manager: SlotsManager, docker_node_id: DockerNodeId
) -> None:
    # acquire all available locks
    slots = await slots_manager._get_node_slots(docker_node_id)
    assert slots == slots_manager.concurrent_saves

    tasks = [
        asyncio.create_task(
            _assert_lock_acquired_and_released(
                slots_manager, docker_node_id, sleep_before_release=1
            )
        )
        for _ in range(slots)
    ]

    # ensure locks are acquired
    await asyncio.sleep(0.25)

    # no slots available
    with pytest.raises(LockAcquireError) as exec_info:
        await _assert_lock_acquired_and_released(
            slots_manager, docker_node_id, sleep_before_release=0
        )
    assert (
        f"{exec_info.value}"
        == f"Could not acquire a lock for {docker_node_id} since all {slots} slots are used."
    )

    # wait for tasks to be released
    await asyncio.gather(*tasks)


@pytest.mark.parametrize(
    "locks_per_node",
    [
        4,
        10,
        100,
    ],
)
async def test_acquire_all_available_node_locks_stress_test(
    slots_manager: SlotsManager,
    docker_node_id: DockerNodeId,
    locks_per_node: int,
) -> None:
    # NOTE: this test is designed to spot if there are any issues when
    # acquiring and releasing locks in parallel with high concurrency

    # adds more stress with lower lock_timeout_s
    slots_manager.lock_timeout_s = 1.0

    slots_manager.concurrent_saves = locks_per_node

    total_node_slots = await slots_manager._get_node_slots(docker_node_id)
    assert total_node_slots == locks_per_node

    # THE extend task is causing things to hang!!! that is what is wrong here!
    await asyncio.gather(
        *[
            _assert_lock_acquired_and_released(
                slots_manager,
                docker_node_id,
                sleep_before_release=slots_manager.lock_timeout_s / 2,
            )
            for _ in range(total_node_slots)
        ]
    )
    print("all locks have been released")


async def test_lock_extension_expiration(
    slots_manager: SlotsManager, docker_node_id: DockerNodeId
) -> None:
    SHORT_INTERVAL = 0.10

    slots_manager.lock_timeout_s = SHORT_INTERVAL
    slots_manager.concurrent_saves = 1

    with pytest.raises(LockNotOwnedError) as err_info:
        async with slots_manager.lock(
            docker_node_id, resource_name=TEST_RESOURCE
        ) as extend_lock:
            # lock should have been extended at least 2 times
            # and should still be locked
            await asyncio.sleep(SHORT_INTERVAL * 4)
            assert await extend_lock._redis_lock.locked() is True
            assert await extend_lock._redis_lock.owned() is True

            # emulating process died (equivalent to no further renews)
            assert extend_lock.task
            extend_lock.task.cancel()
            with suppress(CancelledError):
                await extend_lock.task

            # lock is expected to be unlocked after timeout interval
            await asyncio.sleep(slots_manager.lock_timeout_s)
            assert await extend_lock._redis_lock.locked() is False
            assert await extend_lock._redis_lock.owned() is False

    # since the lock expired we expect the lock to no longer be owned
    assert (
        err_info.traceback[-1].statement.__str__().strip()
        == 'raise LockNotOwnedError("Cannot release a lock" " that\'s no longer owned")'
    )
    # the error must be raised by the release method inside the ExtendLock
    assert (
        err_info.traceback[-2].statement.__str__().strip()
        == "await self._redis_lock.release()"
    )


async def test_lock_raises_error_if_no_slots_are_available(
    slots_manager: SlotsManager, docker_node_id: DockerNodeId
) -> None:
    slots_manager.concurrent_saves = 0

    with pytest.raises(LockAcquireError) as err_info:
        async with slots_manager.lock(docker_node_id, resource_name=TEST_RESOURCE):
            pass

    assert f"{err_info.value}" == (
        f"Could not acquire a lock for {docker_node_id} since all "
        f"{slots_manager.concurrent_saves} slots are used."
    )
