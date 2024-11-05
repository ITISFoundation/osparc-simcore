# pylint:disable=redefined-outer-name
# pylint:disable=unused-argument

from collections.abc import Callable
from datetime import timedelta
from typing import Any, Final, NamedTuple
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
from pydantic import NonNegativeInt, TypeAdapter
from pytest_simcore.helpers.typing_env import EnvVarsDict
from servicelib.deferred_tasks import TaskUID
from servicelib.utils import limited_gather
from settings_library.redis import RedisSettings
from simcore_service_dynamic_scheduler.services.service_tracker import (
    get_all_tracked_services,
    get_tracked_service,
    remove_tracked_service,
    set_if_status_changed_for_service,
    set_request_as_running,
    set_request_as_stopped,
    set_service_status_task_uid,
)
from simcore_service_dynamic_scheduler.services.service_tracker._api import (
    _LOW_RATE_POLL_INTERVAL,
    NORMAL_RATE_POLL_INTERVAL,
    _get_current_scheduler_service_state,
    _get_poll_interval,
)
from simcore_service_dynamic_scheduler.services.service_tracker._models import (
    SchedulerServiceState,
    UserRequestedState,
)

pytest_simcore_core_services_selection = [
    "redis",
]
pytest_simcore_ops_services_selection = [
    # "redis-commander",
]


@pytest.fixture
def app_environment(
    disable_rabbitmq_setup: None,
    disable_deferred_manager_setup: None,
    disable_notifier_setup: None,
    disable_status_monitor_setup: None,
    app_environment: EnvVarsDict,
    redis_service: RedisSettings,
    remove_redis_data: None,
) -> EnvVarsDict:
    return app_environment


async def test_services_tracer_set_as_running_set_as_stopped(
    app: FastAPI,
    node_id: NodeID,
    get_dynamic_service_start: Callable[[NodeID], DynamicServiceStart],
    get_dynamic_service_stop: Callable[[NodeID], DynamicServiceStop],
):
    async def _remove_service() -> None:
        await remove_tracked_service(app, node_id)
        assert await get_tracked_service(app, node_id) is None
        assert await get_all_tracked_services(app) == {}

    async def _set_as_running() -> None:
        await set_request_as_running(app, get_dynamic_service_start(node_id))
        tracked_model = await get_tracked_service(app, node_id)
        assert tracked_model
        assert tracked_model.requested_state == UserRequestedState.RUNNING

    async def _set_as_stopped() -> None:
        await set_request_as_stopped(app, get_dynamic_service_stop(node_id))
        tracked_model = await get_tracked_service(app, node_id)
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
    await limited_gather(
        *[
            set_request_as_stopped(app, get_dynamic_service_stop(uuid4()))
            for _ in range(item_count)
        ],
        limit=100,
    )
    assert len(await get_all_tracked_services(app)) == item_count


@pytest.mark.parametrize(
    "status",
    [
        *[
            NodeGet.model_validate(o)
            for o in NodeGet.model_config["json_schema_extra"]["examples"]
        ],
        *[
            DynamicServiceGet.model_validate(o)
            for o in DynamicServiceGet.model_config["json_schema_extra"]["examples"]
        ],
        NodeGetIdle.model_validate(
            NodeGetIdle.model_config["json_schema_extra"]["example"]
        ),
    ],
)
async def test_set_if_status_changed(
    app: FastAPI,
    node_id: NodeID,
    status: NodeGet | DynamicServiceGet | NodeGetIdle,
    get_dynamic_service_start: Callable[[NodeID], DynamicServiceStart],
):
    await set_request_as_running(app, get_dynamic_service_start(node_id))

    assert await set_if_status_changed_for_service(app, node_id, status) is True

    assert await set_if_status_changed_for_service(app, node_id, status) is False

    model = await get_tracked_service(app, node_id)
    assert model

    assert model.service_status == status.model_dump_json()


async def test_set_service_status_task_uid(
    app: FastAPI,
    node_id: NodeID,
    faker: Faker,
    get_dynamic_service_start: Callable[[NodeID], DynamicServiceStart],
):
    await set_request_as_running(app, get_dynamic_service_start(node_id))

    task_uid = TaskUID(faker.uuid4())
    await set_service_status_task_uid(app, node_id, task_uid)

    model = await get_tracked_service(app, node_id)
    assert model

    assert model.service_status_task_uid == task_uid


@pytest.mark.parametrize(
    "status, expected_poll_interval",
    [
        (
            TypeAdapter(NodeGet).validate_python(
                NodeGet.model_config["json_schema_extra"]["examples"][1]
            ),
            _LOW_RATE_POLL_INTERVAL,
        ),
        *[
            (
                TypeAdapter(DynamicServiceGet).validate_python(o),
                NORMAL_RATE_POLL_INTERVAL,
            )
            for o in DynamicServiceGet.model_config["json_schema_extra"]["examples"]
        ],
        (
            TypeAdapter(NodeGetIdle).validate_python(
                NodeGetIdle.model_config["json_schema_extra"]["example"]
            ),
            _LOW_RATE_POLL_INTERVAL,
        ),
    ],
)
def test__get_poll_interval(
    status: NodeGet | DynamicServiceGet | NodeGetIdle, expected_poll_interval: timedelta
):
    assert _get_poll_interval(status) == expected_poll_interval


def _get_node_get_from(service_state: ServiceState) -> NodeGet:
    dict_data = NodeGet.model_config["json_schema_extra"]["examples"][1]
    assert "service_state" in dict_data
    dict_data["service_state"] = service_state
    return TypeAdapter(NodeGet).validate_python(dict_data)


def _get_dynamic_service_get_from(
    service_state: ServiceState,
) -> DynamicServiceGet:
    dict_data = DynamicServiceGet.model_config["json_schema_extra"]["examples"][1]
    assert "state" in dict_data
    dict_data["state"] = service_state
    return TypeAdapter(DynamicServiceGet).validate_python(dict_data)


def _get_node_get_idle() -> NodeGetIdle:
    return TypeAdapter(NodeGetIdle).validate_python(
        NodeGetIdle.model_config["json_schema_extra"]["example"]
    )


def __get_flat_list(nested_list: list[list[Any]]) -> list[Any]:
    return [item for sublist in nested_list for item in sublist]


class ServiceStatusToSchedulerState(NamedTuple):
    requested: UserRequestedState
    service_status: NodeGet | DynamicServiceGet | NodeGetIdle
    expected: SchedulerServiceState


_EXPECTED_TEST_CASES: list[list[ServiceStatusToSchedulerState]] = [
    [
        # UserRequestedState.RUNNING
        ServiceStatusToSchedulerState(
            UserRequestedState.RUNNING,
            status_generator(ServiceState.PENDING),
            SchedulerServiceState.STARTING,
        ),
        ServiceStatusToSchedulerState(
            UserRequestedState.RUNNING,
            status_generator(ServiceState.PULLING),
            SchedulerServiceState.STARTING,
        ),
        ServiceStatusToSchedulerState(
            UserRequestedState.RUNNING,
            status_generator(ServiceState.STARTING),
            SchedulerServiceState.STARTING,
        ),
        ServiceStatusToSchedulerState(
            UserRequestedState.RUNNING,
            status_generator(ServiceState.RUNNING),
            SchedulerServiceState.RUNNING,
        ),
        ServiceStatusToSchedulerState(
            UserRequestedState.RUNNING,
            status_generator(ServiceState.COMPLETE),
            SchedulerServiceState.UNEXPECTED_OUTCOME,
        ),
        ServiceStatusToSchedulerState(
            UserRequestedState.RUNNING,
            status_generator(ServiceState.FAILED),
            SchedulerServiceState.UNEXPECTED_OUTCOME,
        ),
        ServiceStatusToSchedulerState(
            UserRequestedState.RUNNING,
            status_generator(ServiceState.STOPPING),
            SchedulerServiceState.UNEXPECTED_OUTCOME,
        ),
        ServiceStatusToSchedulerState(
            UserRequestedState.RUNNING,
            _get_node_get_idle(),
            SchedulerServiceState.IDLE,
        ),
        # UserRequestedState.STOPPED
        ServiceStatusToSchedulerState(
            UserRequestedState.STOPPED,
            status_generator(ServiceState.PENDING),
            SchedulerServiceState.UNEXPECTED_OUTCOME,
        ),
        ServiceStatusToSchedulerState(
            UserRequestedState.STOPPED,
            status_generator(ServiceState.PULLING),
            SchedulerServiceState.UNEXPECTED_OUTCOME,
        ),
        ServiceStatusToSchedulerState(
            UserRequestedState.STOPPED,
            status_generator(ServiceState.STARTING),
            SchedulerServiceState.UNEXPECTED_OUTCOME,
        ),
        ServiceStatusToSchedulerState(
            UserRequestedState.STOPPED,
            status_generator(ServiceState.RUNNING),
            SchedulerServiceState.STOPPING,
        ),
        ServiceStatusToSchedulerState(
            UserRequestedState.STOPPED,
            status_generator(ServiceState.COMPLETE),
            SchedulerServiceState.STOPPING,
        ),
        ServiceStatusToSchedulerState(
            UserRequestedState.STOPPED,
            status_generator(ServiceState.FAILED),
            SchedulerServiceState.UNEXPECTED_OUTCOME,
        ),
        ServiceStatusToSchedulerState(
            UserRequestedState.STOPPED,
            status_generator(ServiceState.STOPPING),
            SchedulerServiceState.STOPPING,
        ),
        ServiceStatusToSchedulerState(
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
_FLAT_EXPECTED_TEST_CASES: list[ServiceStatusToSchedulerState] = __get_flat_list(
    _EXPECTED_TEST_CASES
)
# ensure enum changes do not break above rules
_NODE_STATUS_FORMATS_COUNT: Final[int] = 2
assert (
    len(_FLAT_EXPECTED_TEST_CASES)
    == len(ServiceState) * len(UserRequestedState) * _NODE_STATUS_FORMATS_COUNT
)


@pytest.mark.parametrize("service_status_to_scheduler_state", _FLAT_EXPECTED_TEST_CASES)
def test__get_current_scheduler_service_state(
    service_status_to_scheduler_state: ServiceStatusToSchedulerState,
):
    assert (
        _get_current_scheduler_service_state(
            service_status_to_scheduler_state.requested,
            service_status_to_scheduler_state.service_status,
        )
        == service_status_to_scheduler_state.expected
    )
