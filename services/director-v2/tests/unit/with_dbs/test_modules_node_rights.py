# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=protected-access

import asyncio
from asyncio import CancelledError, Task
from contextlib import suppress
from typing import Any, AsyncIterable, Final

import pytest
from asgi_lifespan import LifespanManager
from faker import Faker
from fastapi import FastAPI
from pydantic import PositiveFloat
from pytest import MonkeyPatch
from redis.exceptions import LockError, LockNotOwnedError
from settings_library.redis import RedisSettings
from simcore_service_director_v2.core.errors import NodeRightsAcquireError
from simcore_service_director_v2.core.settings import AppSettings
from simcore_service_director_v2.modules import node_rights
from simcore_service_director_v2.modules.node_rights import (
    DockerNodeId,
    ExtendLock,
    NodeRightsManager,
    ResourceName,
)

pytest_simcore_core_services_selection = [
    "redis",
]


# UTILS
TEST_RESOURCE: Final[ResourceName] = "a_resource"


async def _assert_lock_acquired_and_released(
    node_rights_manager: NodeRightsManager,
    docker_node_id: DockerNodeId,
    resource_name: ResourceName,
    *,
    sleep_before_release: PositiveFloat,
) -> ExtendLock:
    async with node_rights_manager.acquire(
        docker_node_id, resource_name=resource_name
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


@pytest.fixture
async def minimal_app(
    project_env_devel_environment: dict[str, Any],
    redis_settings: RedisSettings,
    monkeypatch: MonkeyPatch,
) -> AsyncIterable[FastAPI]:
    monkeypatch.setenv("REDIS_HOST", redis_settings.REDIS_HOST)
    monkeypatch.setenv("REDIS_PORT", f"{redis_settings.REDIS_PORT}")
    monkeypatch.setenv("DYNAMIC_SIDECAR_DOCKER_NODE_RESOURCE_LIMITS_ENABLED", "true")

    app = FastAPI()

    # add expected redis_settings
    app.state.settings = AppSettings.create_from_envs()

    # setup redis module
    node_rights.setup(app)

    async with LifespanManager(app):
        yield app


@pytest.fixture
async def node_rights_manager(minimal_app: FastAPI) -> AsyncIterable[NodeRightsManager]:
    redis_lock_manger = await NodeRightsManager.instance(minimal_app)
    await redis_lock_manger.redis_client_sdk.redis.flushall()
    yield redis_lock_manger
    await redis_lock_manger.redis_client_sdk.redis.flushall()


@pytest.fixture
def docker_node_id(faker: Faker) -> str:
    return faker.uuid4()


async def test_redis_lock_working_as_expected(
    node_rights_manager: NodeRightsManager, docker_node_id
) -> None:
    lock = node_rights_manager.redis_client_sdk.redis.lock(docker_node_id)

    lock_acquired = await lock.acquire(blocking=False)
    assert lock_acquired
    assert await lock.locked() is True

    await lock.release()
    assert await lock.locked() is False

    with pytest.raises(LockError):
        await lock.release()


async def test_redis_two_lock_instances(
    node_rights_manager: NodeRightsManager, docker_node_id: DockerNodeId
) -> None:
    # NOTE: this test show cases how the locks work
    # you have to acquire the lock from the same istance
    # in order to avoid tricky situations

    lock = node_rights_manager.redis_client_sdk.redis.lock(docker_node_id)

    lock_acquired = await lock.acquire(blocking=False)
    assert lock_acquired
    assert await lock.locked() is True

    # we get a different instance
    second_lock = node_rights_manager.redis_client_sdk.redis.lock(docker_node_id)
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
    node_rights_manager: NodeRightsManager, docker_node_id: DockerNodeId
) -> None:
    extend_lock = await _assert_lock_acquired_and_released(
        node_rights_manager, docker_node_id, TEST_RESOURCE, sleep_before_release=0
    )

    # try to cancel again will not work!
    with pytest.raises(LockError):
        await node_rights_manager._release_extend_lock(extend_lock)


@pytest.mark.parametrize("resource_count", [1, 2, 10])
async def test_no_more_locks_can_be_acquired(
    node_rights_manager: NodeRightsManager,
    docker_node_id: DockerNodeId,
    resource_count: int,
) -> None:
    # acquire all available locks

    async def _acquire_tasks(resource_name: ResourceName) -> tuple[int, list[Task]]:
        slots = await node_rights_manager._get_node_slots(docker_node_id, resource_name)
        assert slots == node_rights_manager.concurrent_resource_slots

        tasks = [
            asyncio.create_task(
                _assert_lock_acquired_and_released(
                    node_rights_manager,
                    docker_node_id,
                    resource_name,
                    sleep_before_release=1,
                )
            )
            for _ in range(slots)
        ]

        # ensure locks are acquired
        await asyncio.sleep(0.25)

        # no slots available
        with pytest.raises(NodeRightsAcquireError) as exec_info:
            await _assert_lock_acquired_and_released(
                node_rights_manager,
                docker_node_id,
                resource_name,
                sleep_before_release=0,
            )
        assert (
            f"{exec_info.value}"
            == f"Could not acquire a lock for {docker_node_id} since all {slots} slots are used."
        )
        return slots, tasks

    tasks = []
    for r in range(resource_count):
        resource_name = f"resource_{r}"
        used_slots_r1, resource_tasks = await _acquire_tasks(resource_name)
        assert len(resource_tasks) == used_slots_r1
        tasks += resource_tasks

    # wait for tasks to be released
    await asyncio.gather(*tasks)


@pytest.mark.skip(
    reason="fails will be removed by @GitHK, see https://github.com/ITISFoundation/osparc-simcore/issues/4405"
)
@pytest.mark.flaky(max_runs=3)
@pytest.mark.parametrize(
    "locks_per_node",
    [
        4,
        10,
        100,
    ],
)
async def test_acquire_all_available_node_locks_stress_test(
    node_rights_manager: NodeRightsManager,
    docker_node_id: DockerNodeId,
    locks_per_node: int,
) -> None:
    # NOTE: this test is designed to spot if there are any issues when
    # acquiring and releasing locks in parallel with high concurrency

    # adds more stress with lower lock_timeout_s
    node_rights_manager.lock_timeout_s = 0.5

    node_rights_manager.concurrent_resource_slots = locks_per_node

    total_node_slots = await node_rights_manager._get_node_slots(
        docker_node_id, TEST_RESOURCE
    )
    assert total_node_slots == locks_per_node

    # THE extend task is causing things to hang!!! that is what is wrong here!
    await asyncio.gather(
        *[
            _assert_lock_acquired_and_released(
                node_rights_manager,
                docker_node_id,
                TEST_RESOURCE,
                sleep_before_release=node_rights_manager.lock_timeout_s * 2,
            )
            for _ in range(total_node_slots)
        ]
    )
    print("all locks have been released")


async def test_lock_extension_expiration(
    node_rights_manager: NodeRightsManager, docker_node_id: DockerNodeId
) -> None:
    SHORT_INTERVAL = 0.10

    node_rights_manager.lock_timeout_s = SHORT_INTERVAL
    node_rights_manager.concurrent_resource_slots = 1

    with pytest.raises(LockNotOwnedError, match="Cannot release a lock") as err_info:
        async with node_rights_manager.acquire(
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
            await asyncio.sleep(node_rights_manager.lock_timeout_s)
            assert await extend_lock._redis_lock.locked() is False
            assert await extend_lock._redis_lock.owned() is False

    # the error must be raised by the release method inside the ExtendLock
    assert (
        err_info.traceback[-2].statement.__str__().strip()
        == "await self._redis_lock.release()"
    )


async def test_lock_raises_error_if_no_slots_are_available(
    node_rights_manager: NodeRightsManager, docker_node_id: DockerNodeId
) -> None:
    node_rights_manager.concurrent_resource_slots = 0

    with pytest.raises(NodeRightsAcquireError) as err_info:
        async with node_rights_manager.acquire(
            docker_node_id, resource_name=TEST_RESOURCE
        ):
            pass

    assert f"{err_info.value}" == (
        f"Could not acquire a lock for {docker_node_id} since all "
        f"{node_rights_manager.concurrent_resource_slots} slots are used."
    )
