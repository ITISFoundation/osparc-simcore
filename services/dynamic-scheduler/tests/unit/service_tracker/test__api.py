# pylint:disable=redefined-outer-name
# pylint:disable=unused-argument

from collections.abc import Callable
from datetime import timedelta
from typing import Any, Final
from uuid import uuid4

import pytest
from faker import Faker
from fastapi import FastAPI
from models_library.api_schemas_directorv2.dynamic_services import DynamicServiceGet
from models_library.api_schemas_dynamic_scheduler.dynamic_services import (
    DynamicServiceStart,
    DynamicServiceStop,
)
from models_library.api_schemas_webserver.projects_nodes import NodeGet, NodeGetIdle
from models_library.projects_nodes_io import NodeID
from models_library.services_enums import ServiceState
from pydantic import NonNegativeInt
from pytest_simcore.helpers.typing_env import EnvVarsDict
from servicelib.deferred_tasks import TaskUID
from servicelib.utils import logged_gather
from settings_library.redis import RedisSettings
from simcore_service_dynamic_scheduler.services.service_tracker import (
    get_all_tracked,
    get_tracked,
    remove_tracked,
    set_if_status_changed,
    set_request_as_running,
    set_request_as_stopped,
    set_service_status_task_uid,
)
from simcore_service_dynamic_scheduler.services.service_tracker._api import (
    _LOW_RATE_POLL_INTERVAL,
    NORMAL_RATE_POLL_INTERVAL,
    _get_current_state,
    _get_poll_interval,
)
from simcore_service_dynamic_scheduler.services.service_tracker._models import (
    SchedulerServiceState,
    UserRequestedState,
)

pytest_simcore_core_services_selection = [
    "redis",
]


@pytest.fixture
def app_environment(
    disable_rabbitmq_setup: None,
    disable_deferred_manager_setup: None,
    disable_notifier_setup: None,
    app_environment: EnvVarsDict,
    redis_service: RedisSettings,
    remove_redis_data: None,
) -> EnvVarsDict:
    return app_environment


@pytest.fixture
def node_id() -> NodeID:
    return uuid4()


async def test_services_tracer_set_as_running_set_as_stopped(
    app: FastAPI,
    node_id: NodeID,
    get_dynamic_service_start: Callable[[NodeID], DynamicServiceStart],
    get_dynamic_service_stop: Callable[[NodeID], DynamicServiceStop],
):
    async def _remove_service() -> None:
        await remove_tracked(app, node_id)
        assert await get_tracked(app, node_id) is None
        assert await get_all_tracked(app) == {}

    async def _set_as_running() -> None:
        await set_request_as_running(app, get_dynamic_service_start(node_id))
        tracked_model = await get_tracked(app, node_id)
        assert tracked_model
        assert tracked_model.requested_state == UserRequestedState.RUNNING

    async def _set_as_stopped() -> None:
        await set_request_as_stopped(app, get_dynamic_service_stop(node_id))
        tracked_model = await get_tracked(app, node_id)
        assert tracked_model
        assert tracked_model.requested_state == UserRequestedState.STOPPED

    # request as running then as stopped
    await _remove_service()
    await _set_as_running()
    await _set_as_stopped()

    # request as stopped then as running
    await _remove_service()
    await _set_as_stopped()
    await _set_as_running()


@pytest.mark.parametrize("item_count", [100])
async def test_services_tracer_workflow(
    app: FastAPI,
    node_id: NodeID,
    item_count: NonNegativeInt,
    get_dynamic_service_start: Callable[[NodeID], DynamicServiceStart],
    get_dynamic_service_stop: Callable[[NodeID], DynamicServiceStop],
):
    # ensure more than one service can be tracked
    await logged_gather(
        *[
            set_request_as_stopped(app, get_dynamic_service_stop(uuid4()))
            for _ in range(item_count)
        ],
        max_concurrency=100,
    )
    assert len(await get_all_tracked(app)) == item_count


@pytest.mark.parametrize(
    "status",
    [
        *[NodeGet.parse_obj(x) for x in NodeGet.Config.schema_extra["examples"]],
        *[
            DynamicServiceGet.parse_obj(x)
            for x in DynamicServiceGet.Config.schema_extra["examples"]
        ],
        NodeGetIdle.parse_obj(NodeGetIdle.Config.schema_extra["example"]),
    ],
)
async def test_set_if_status_changed(
    app: FastAPI,
    node_id: NodeID,
    status: NodeGet | DynamicServiceGet | NodeGetIdle,
    get_dynamic_service_start: Callable[[NodeID], DynamicServiceStart],
):
    await set_request_as_running(app, get_dynamic_service_start(node_id))

    assert await set_if_status_changed(app, node_id, status) is True

    assert await set_if_status_changed(app, node_id, status) is False

    model = await get_tracked(app, node_id)
    assert model

    assert model.service_status == status.json()


async def test_set_service_status_task_uid(
    app: FastAPI,
    node_id: NodeID,
    faker: Faker,
    get_dynamic_service_start: Callable[[NodeID], DynamicServiceStart],
):
    await set_request_as_running(app, get_dynamic_service_start(node_id))

    task_uid = TaskUID(faker.uuid4())
    await set_service_status_task_uid(app, node_id, task_uid)

    model = await get_tracked(app, node_id)
    assert model

    assert model.service_status_task_uid == task_uid


@pytest.mark.parametrize(
    "status, expected_poll_interval",
    [
        (
            NodeGet.parse_obj(NodeGet.Config.schema_extra["examples"][1]),
            _LOW_RATE_POLL_INTERVAL,
        ),
        *[
            (DynamicServiceGet.parse_obj(x), NORMAL_RATE_POLL_INTERVAL)
            for x in DynamicServiceGet.Config.schema_extra["examples"]
        ],
        (
            NodeGetIdle.parse_obj(NodeGetIdle.Config.schema_extra["example"]),
            _LOW_RATE_POLL_INTERVAL,
        ),
    ],
)
def test__get_poll_interval(
    status: NodeGet | DynamicServiceGet | NodeGetIdle, expected_poll_interval: timedelta
):
    assert _get_poll_interval(status) == expected_poll_interval


def _get_node_get_from(service_state: ServiceState) -> NodeGet:
    dict_data = NodeGet.Config.schema_extra["examples"][1]
    assert "service_state" in dict_data
    dict_data["service_state"] = service_state
    return NodeGet.parse_obj(dict_data)


def _get_dynamic_service_get_from(
    service_state: DynamicServiceGet,
) -> DynamicServiceGet:
    dict_data = DynamicServiceGet.Config.schema_extra["examples"][1]
    assert "state" in dict_data
    dict_data["state"] = service_state
    return DynamicServiceGet.parse_obj(dict_data)


def _get_node_get_idle() -> NodeGetIdle:
    return NodeGetIdle.parse_obj(NodeGetIdle.Config.schema_extra["example"])


def __get_flat_list(nested_list: list[list[Any]]) -> list[Any]:
    return [item for sublist in nested_list for item in sublist]


_EXPECTED_TEST_CASES: list[list[tuple]] = [
    [
        # UserRequestedState.RUNNING
        (
            UserRequestedState.RUNNING,
            status_generator(ServiceState.PENDING),
            SchedulerServiceState.STARTING,
        ),
        (
            UserRequestedState.RUNNING,
            status_generator(ServiceState.PULLING),
            SchedulerServiceState.STARTING,
        ),
        (
            UserRequestedState.RUNNING,
            status_generator(ServiceState.STARTING),
            SchedulerServiceState.STARTING,
        ),
        (
            UserRequestedState.RUNNING,
            status_generator(ServiceState.RUNNING),
            SchedulerServiceState.RUNNING,
        ),
        (
            UserRequestedState.RUNNING,
            status_generator(ServiceState.COMPLETE),
            SchedulerServiceState.UNEXPECTED_OUTCOME,
        ),
        (
            UserRequestedState.RUNNING,
            status_generator(ServiceState.FAILED),
            SchedulerServiceState.UNEXPECTED_OUTCOME,
        ),
        (
            UserRequestedState.RUNNING,
            status_generator(ServiceState.STOPPING),
            SchedulerServiceState.UNEXPECTED_OUTCOME,
        ),
        (
            UserRequestedState.RUNNING,
            _get_node_get_idle(),
            SchedulerServiceState.IDLE,
        ),
        # UserRequestedState.STOPPED
        (
            UserRequestedState.STOPPED,
            status_generator(ServiceState.PENDING),
            SchedulerServiceState.UNEXPECTED_OUTCOME,
        ),
        (
            UserRequestedState.STOPPED,
            status_generator(ServiceState.PULLING),
            SchedulerServiceState.UNEXPECTED_OUTCOME,
        ),
        (
            UserRequestedState.STOPPED,
            status_generator(ServiceState.STARTING),
            SchedulerServiceState.UNEXPECTED_OUTCOME,
        ),
        (
            UserRequestedState.STOPPED,
            status_generator(ServiceState.RUNNING),
            SchedulerServiceState.STOPPING,
        ),
        (
            UserRequestedState.STOPPED,
            status_generator(ServiceState.COMPLETE),
            SchedulerServiceState.STOPPING,
        ),
        (
            UserRequestedState.STOPPED,
            status_generator(ServiceState.FAILED),
            SchedulerServiceState.UNEXPECTED_OUTCOME,
        ),
        (
            UserRequestedState.STOPPED,
            status_generator(ServiceState.STOPPING),
            SchedulerServiceState.STOPPING,
        ),
        (
            UserRequestedState.STOPPED,
            _get_node_get_idle(),
            SchedulerServiceState.IDLE,
        ),
    ]
    for status_generator in (
        _get_node_get_from,
        _get_dynamic_service_get_from,
    )
]
_FLAT_EXPECTED_TEST_CASES = __get_flat_list(_EXPECTED_TEST_CASES)
# ensure enum changes do not break above rules
_IDLE_ITEM_COUNT: Final[int] = 1
_NODE_STATUS_FORMATS_COUNT: Final[int] = 2
assert (
    len(_FLAT_EXPECTED_TEST_CASES)
    == (len(ServiceState) + _IDLE_ITEM_COUNT)
    * len(UserRequestedState)
    * _NODE_STATUS_FORMATS_COUNT
)


@pytest.mark.parametrize("requested_state, status, expected", _FLAT_EXPECTED_TEST_CASES)
def test__get_current_state(
    requested_state: UserRequestedState,
    status: NodeGet | DynamicServiceGet | NodeGetIdle,
    expected: SchedulerServiceState,
):
    assert _get_current_state(requested_state, status) == expected