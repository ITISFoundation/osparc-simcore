# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

import asyncio
from collections.abc import AsyncIterable, Awaitable, Callable
from datetime import timedelta
from typing import Final

import pytest
from faker import Faker
from fastapi import FastAPI
from models_library.projects_nodes_io import NodeID
from pydantic import NonNegativeInt
from pytest_mock import MockerFixture
from pytest_simcore.helpers.typing_env import EnvVarsDict
from settings_library.redis import RedisSettings
from simcore_service_dynamic_scheduler.services.p_scheduler._models import SchedulerServiceStatus
from simcore_service_dynamic_scheduler.services.p_scheduler._node_status._manager import (
    _PERIODIC_HANDLING_MESSAGE,
    StatusManager,
)

_FAST_STATUS_TTL_CACHE: Final[timedelta] = timedelta(seconds=0.1)
_TTL_SECONDS = _FAST_STATUS_TTL_CACHE.total_seconds()
_TTL_MS = int(_TTL_SECONDS * 1000)
_FAST_UPDATE_STATUSES_INTERVAL: Final[timedelta] = timedelta(seconds=0.15)
_MAX_PARALLEL_UPDATES: Final[NonNegativeInt] = 20


@pytest.fixture
def node_id(faker: Faker) -> NodeID:
    return faker.uuid4(cast_to=None)


@pytest.fixture
def scheduler_status() -> SchedulerServiceStatus:
    return SchedulerServiceStatus.IS_PRESENT


@pytest.fixture
def mock__get_scheduler_service_status(mocker: MockerFixture, scheduler_status: SchedulerServiceStatus) -> None:
    mocker.patch(
        "simcore_service_dynamic_scheduler.services.p_scheduler._node_status._manager._status.get_scheduler_service_status",
        return_value=scheduler_status,
    )


@pytest.fixture
def app_environment(
    disable_generic_scheduler_lifespan: None,
    disable_postgres_lifespan: None,
    disable_rabbitmq_lifespan: None,
    disable_deferred_manager_lifespan: None,
    disable_notifier_lifespan: None,
    disable_status_monitor_lifespan: None,
    disable_p_scheduler_lifespan: None,
    use_in_memory_redis: RedisSettings,
    app_environment: EnvVarsDict,
) -> EnvVarsDict:
    return app_environment


@pytest.fixture
async def status_manager(app: FastAPI) -> AsyncIterable[StatusManager]:
    manager = StatusManager(
        app,
        status_ttl=_FAST_STATUS_TTL_CACHE,
        update_statuses_interval=_FAST_UPDATE_STATUSES_INTERVAL,
        max_parallel_updates=_MAX_PARALLEL_UPDATES,
    )
    await manager.setup()
    yield manager
    await manager.shutdown()


async def _wait_for_keys_to_expire() -> None:
    await asyncio.sleep(_TTL_SECONDS * 1.1)


async def test__redis_interface(
    mock__get_scheduler_service_status: None,
    status_manager: StatusManager,
    scheduler_status: SchedulerServiceStatus,
    node_id: NodeID,
):
    redis_interface = status_manager.redis_interface

    # 1. get and set check
    assert await redis_interface.get_status(node_id) is None

    await redis_interface.set_status(node_id, scheduler_status, ttl_milliseconds=_TTL_MS)
    assert await redis_interface.get_status(node_id) == scheduler_status
    await _wait_for_keys_to_expire()
    assert await redis_interface.get_status(node_id) is None

    assert await redis_interface.get_all_tracked() == set()

    # 2. tracking and untracking check

    await redis_interface.track(node_id)
    assert await redis_interface.get_all_tracked() == {node_id}
    await redis_interface.untrack(node_id)
    assert await redis_interface.get_all_tracked() == set()


def _assert_no_cache_log(caplog: pytest.LogCaptureFixture, node_id: NodeID) -> None:
    assert f"'{node_id}' not found in redis cache" not in caplog.text


def _assert_cache_log_found(caplog: pytest.LogCaptureFixture, node_id: NodeID) -> None:
    assert f"'{node_id}' not found in redis cache" in caplog.text


@pytest.fixture
async def assert_scheduler_status(
    status_manager: StatusManager, scheduler_status: SchedulerServiceStatus, node_id: NodeID
) -> Callable[[], Awaitable[None]]:
    async def _() -> None:
        scheduler_service_status = await status_manager.get_scheduler_service_status(node_id)
        assert scheduler_service_status == scheduler_status

    return _


@pytest.fixture
async def run_worker_update_scheduler_service_status(status_manager: StatusManager) -> Callable[[], Awaitable[None]]:
    async def _() -> None:
        await status_manager._worker_update_scheduler_service_status()  # noqa: SLF001

    return _


async def test_status_manager(
    mock__get_scheduler_service_status: None,
    status_manager: StatusManager,
    scheduler_status: SchedulerServiceStatus,
    node_id: NodeID,
    caplog: pytest.LogCaptureFixture,
    assert_scheduler_status: Callable[[], Awaitable[None]],
    run_worker_update_scheduler_service_status: Callable[[], Awaitable[None]],
):
    caplog.set_level("DEBUG")

    # 1. check status not coming from Redis

    caplog.clear()
    _assert_no_cache_log(caplog, node_id)

    await assert_scheduler_status()
    _assert_cache_log_found(caplog, node_id)

    # 2. check status comes from Redis (no external call, no log message)
    caplog.clear()

    await status_manager.set_tracked_services({node_id})
    assert await status_manager.redis_interface.get_all_tracked() == {node_id}

    # register service
    await run_worker_update_scheduler_service_status()
    await assert_scheduler_status()
    _assert_no_cache_log(caplog, node_id)

    await status_manager.set_tracked_services(set())
    assert await status_manager.redis_interface.get_all_tracked() == set()

    # deregister service
    await run_worker_update_scheduler_service_status()
    await _wait_for_keys_to_expire()
    _assert_no_cache_log(caplog, node_id)

    await assert_scheduler_status()
    _assert_cache_log_found(caplog, node_id)


@pytest.fixture
async def status_managers(app: FastAPI) -> AsyncIterable[list[StatusManager]]:
    managers: list[StatusManager] = []

    for _ in range(10):
        manager = StatusManager(
            app,
            status_ttl=_FAST_STATUS_TTL_CACHE,
            update_statuses_interval=_FAST_UPDATE_STATUSES_INTERVAL,
            max_parallel_updates=_MAX_PARALLEL_UPDATES,
        )
        managers.append(manager)

    for manager in managers:
        await manager.setup()

    yield managers

    for manager in managers:
        await manager.shutdown()


def _ensure_unique_log_message(caplog: pytest.LogCaptureFixture) -> str:
    found_messages = []

    for line in caplog.text.splitlines():
        if _PERIODIC_HANDLING_MESSAGE in line:
            found_messages.append(line)
            print(line)

    assert len(found_messages) > 1
    assert len(set(found_messages)) == 1
    return found_messages.pop()


async def test_status_manager_is_switched_if_killed(
    mock__get_scheduler_service_status: None, status_managers: list[StatusManager], caplog: pytest.LogCaptureFixture
):
    sleep_interval = 0.4
    caplog.set_level("DEBUG")

    # 1. ensure log messages
    await asyncio.sleep(sleep_interval)
    log_message = _ensure_unique_log_message(caplog)

    # 2. get active manager and close it
    logged_manager_id = log_message.split("'")[-2]
    ids_to_managers = {f"{id(manager)}": manager for manager in status_managers}
    status_manager = ids_to_managers[logged_manager_id]
    await status_manager.shutdown()
    caplog.clear()

    # 3. another manager should take over and log a message (different from the previous one)
    await asyncio.sleep(sleep_interval)
    new_log_message = _ensure_unique_log_message(caplog)

    # messages are different
    assert new_log_message != log_message
