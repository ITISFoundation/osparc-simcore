# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

import asyncio
from collections.abc import AsyncIterable, Awaitable, Callable
from datetime import timedelta
from typing import Final
from unittest.mock import AsyncMock

import pytest
from faker import Faker
from fastapi import FastAPI
from models_library.api_schemas_directorv2.dynamic_services import DynamicServiceGet
from models_library.api_schemas_webserver.projects_nodes import NodeGet, NodeGetIdle
from models_library.projects_nodes_io import NodeID
from models_library.services_enums import ServiceState
from pydantic import TypeAdapter
from pytest_mock import MockerFixture
from pytest_simcore.helpers.typing_env import EnvVarsDict
from settings_library.redis import RedisSettings
from simcore_service_dynamic_scheduler.services.p_scheduler._models import SchedulerServiceStatus
from simcore_service_dynamic_scheduler.services.p_scheduler._node_status import (
    StatusManager,
    _get_scheduler_service_status,
)

_FAST_STATUS_TTL_CACHE: Final[timedelta] = timedelta(seconds=0.1)
_TTL_SECONDS = _FAST_STATUS_TTL_CACHE.total_seconds()
_TTL_MS = int(_TTL_SECONDS * 1000)
_FAST_UPDATE_STATUSES_INTERVAL: Final[timedelta] = timedelta(seconds=0.15)


@pytest.fixture
def mocked_app() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def node_id(faker: Faker) -> NodeID:
    return faker.uuid4(cast_to=None)


@pytest.fixture
def mock_get_service_status(mocker: MockerFixture, service_status: NodeGet | DynamicServiceGet | NodeGetIdle) -> None:
    mocker.patch(
        "simcore_service_dynamic_scheduler.services.p_scheduler._node_status.get_service_status",
        return_value=service_status,
    )


def _idle() -> NodeGetIdle:
    return TypeAdapter(NodeGetIdle).validate_python(NodeGetIdle.model_json_schema()["examples"][0])


def _dynamic(service_state: ServiceState) -> DynamicServiceGet:
    data = DynamicServiceGet.model_json_schema()["examples"][1]
    data["service_state"] = service_state
    return TypeAdapter(DynamicServiceGet).validate_python(data)


def _node(service_state: ServiceState) -> NodeGet:
    data = NodeGet.model_json_schema()["examples"][1]
    data["service_state"] = service_state
    return TypeAdapter(NodeGet).validate_python(data)


@pytest.mark.parametrize(
    "service_status, expected_scheduler_status",
    [
        # IS_PRESENT
        pytest.param(_dynamic(ServiceState.RUNNING), SchedulerServiceStatus.IS_PRESENT, id="dynamic-RUNNING"),
        pytest.param(_node(ServiceState.RUNNING), SchedulerServiceStatus.IS_PRESENT, id="node-RUNNING"),
        # IN_ERROR
        pytest.param(_dynamic(ServiceState.FAILED), SchedulerServiceStatus.IN_ERROR, id="dynamic-FAILED"),
        pytest.param(_node(ServiceState.FAILED), SchedulerServiceStatus.IN_ERROR, id="node-FAILED"),
        # IS_ABSENT
        pytest.param(_idle(), SchedulerServiceStatus.IS_ABSENT, id="idle"),
        pytest.param(_dynamic(ServiceState.IDLE), SchedulerServiceStatus.IS_ABSENT, id="dynamic-IDLE"),
        pytest.param(_node(ServiceState.IDLE), SchedulerServiceStatus.IS_ABSENT, id="node-IDLE"),
        pytest.param(_dynamic(ServiceState.COMPLETE), SchedulerServiceStatus.IS_ABSENT, id="dynamic-COMPLETE"),
        pytest.param(_node(ServiceState.COMPLETE), SchedulerServiceStatus.IS_ABSENT, id="node-COMPLETE"),
        # TRANSITIONING
        pytest.param(_dynamic(ServiceState.PENDING), SchedulerServiceStatus.TRANSITIONING, id="dynamic-PENDING"),
        pytest.param(_node(ServiceState.PENDING), SchedulerServiceStatus.TRANSITIONING, id="node-PENDING"),
        pytest.param(_dynamic(ServiceState.PULLING), SchedulerServiceStatus.TRANSITIONING, id="dynamic-PULLING"),
        pytest.param(_node(ServiceState.PULLING), SchedulerServiceStatus.TRANSITIONING, id="node-PULLING"),
        pytest.param(_dynamic(ServiceState.STARTING), SchedulerServiceStatus.TRANSITIONING, id="dynamic-STARTING"),
        pytest.param(_node(ServiceState.STARTING), SchedulerServiceStatus.TRANSITIONING, id="node-STARTING"),
        pytest.param(_dynamic(ServiceState.STOPPING), SchedulerServiceStatus.TRANSITIONING, id="dynamic-STOPPING"),
        pytest.param(_node(ServiceState.STOPPING), SchedulerServiceStatus.TRANSITIONING, id="node-STOPPING"),
    ],
)
async def test__get_scheduler_service_status(
    mock_get_service_status: None,
    mocked_app: AsyncMock,
    node_id: NodeID,
    expected_scheduler_status: SchedulerServiceStatus,
):
    assert await _get_scheduler_service_status(mocked_app, node_id) == expected_scheduler_status


@pytest.fixture
def scheduler_status() -> SchedulerServiceStatus:
    return SchedulerServiceStatus.TRANSITIONING


@pytest.fixture
def mock__get_scheduler_service_status(mocker: MockerFixture, scheduler_status: SchedulerServiceStatus) -> None:
    mocker.patch(
        "simcore_service_dynamic_scheduler.services.p_scheduler._node_status._get_scheduler_service_status",
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
    use_in_memory_redis: RedisSettings,
    app_environment: EnvVarsDict,
) -> EnvVarsDict:
    return app_environment


@pytest.fixture
async def status_manager(app: FastAPI) -> AsyncIterable[StatusManager]:
    manager = StatusManager(
        app, status_ttl=_FAST_STATUS_TTL_CACHE, update_statuses_interval=_FAST_UPDATE_STATUSES_INTERVAL
    )
    await manager.setup()
    yield manager
    await manager.teardown()


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
    # wait for key to expire
    await asyncio.sleep(_TTL_SECONDS * 1.1)
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


async def _wait_for__worker_update_scheduler_service_status() -> None:
    await asyncio.sleep(_FAST_UPDATE_STATUSES_INTERVAL.total_seconds() * 2.1)


async def test_status_manager(
    mock__get_scheduler_service_status: None,
    status_manager: StatusManager,
    scheduler_status: SchedulerServiceStatus,
    node_id: NodeID,
    caplog: pytest.LogCaptureFixture,
    assert_scheduler_status: Callable[[], Awaitable[None]],
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

    # wait a bit, it will APPEAR
    await _wait_for__worker_update_scheduler_service_status()

    await assert_scheduler_status()
    _assert_no_cache_log(caplog, node_id)

    await status_manager.set_tracked_services(set())
    assert await status_manager.redis_interface.get_all_tracked() == set()

    # after a bit it will DISAPPEAR
    await _wait_for__worker_update_scheduler_service_status()
    _assert_no_cache_log(caplog, node_id)

    await assert_scheduler_status()
    _assert_cache_log_found(caplog, node_id)
