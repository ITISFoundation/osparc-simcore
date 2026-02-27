# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

from unittest.mock import AsyncMock

import pytest
import pytest_mock
from faker import Faker
from fastapi import FastAPI
from models_library.generated_models.docker_rest_api import TaskState
from models_library.projects_nodes_io import NodeID
from pytest_simcore.helpers.typing_env import EnvVarsDict
from settings_library.redis import RedisSettings
from simcore_service_dynamic_scheduler.services.p_scheduler._node_status._docker import (
    _DOCKER_TASK_STATE_TO_SERVICE_STATE,
    _PREFIX_DY_PROXY,
    _PREFIX_DY_SIDECAR,
    get_services_presence,
)
from simcore_service_dynamic_scheduler.services.p_scheduler._node_status._models import (
    ComponentPresence,
    ServicesPresence,
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
def node_id_legacy(faker: Faker) -> NodeID:
    return faker.uuid4(cast_to=None)


@pytest.fixture
def node_id_new_style_one_of_two(faker: Faker) -> NodeID:
    return faker.uuid4(cast_to=None)


@pytest.fixture
def node_id_new_style_two_of_two(faker: Faker) -> NodeID:
    return faker.uuid4(cast_to=None)


@pytest.fixture
def mocked_minimal_service_data(
    node_id_legacy: NodeID,
    node_id_new_style_one_of_two: NodeID,
    node_id_new_style_two_of_two: NodeID,
) -> dict[NodeID, list[dict]]:
    return {
        node_id_legacy: [
            {
                "Spec": {
                    "Name": f"random_{node_id_legacy}",
                    "Labels": {"io.simcore.runtime.node-id": f"{node_id_legacy}"},
                }
            },
        ],
        node_id_new_style_one_of_two: [
            {
                "Spec": {
                    "Name": f"{_PREFIX_DY_SIDECAR}_{node_id_new_style_one_of_two}",
                    "Labels": {"io.simcore.runtime.node-id": f"{node_id_new_style_one_of_two}"},
                }
            },
        ],
        node_id_new_style_two_of_two: [
            {
                "Spec": {
                    "Name": f"{_PREFIX_DY_SIDECAR}_{node_id_new_style_two_of_two}",
                    "Labels": {"io.simcore.runtime.node-id": f"{node_id_new_style_two_of_two}"},
                }
            },
            {
                "Spec": {
                    "Name": f"{_PREFIX_DY_PROXY}_{node_id_new_style_two_of_two}",
                    "Labels": {"io.simcore.runtime.node-id": f"{node_id_new_style_two_of_two}"},
                }
            },
        ],
    }


@pytest.fixture
async def mock_docker_client(
    mocker: pytest_mock.MockerFixture,
    mocked_minimal_service_data: dict[NodeID, list[dict]],
    task_state: TaskState,
) -> None:
    mock_docker = AsyncMock()
    all_services = [service for services in mocked_minimal_service_data.values() for service in services]

    async def _filter_services(*, filters: dict | None = None) -> list[dict]:
        if filters is None:
            return all_services
        label_filter = filters.get("label", "")
        # parse "io.simcore.runtime.node-id=<uuid>" format
        if "=" in label_filter:
            _key, value = label_filter.split("=", 1)
            return [s for s in all_services if s.get("Spec", {}).get("Labels", {}).get(_key) == value]
        return all_services

    async def _filter_tasks(*, filters: dict | None = None) -> list[dict]:
        # returns a single task with the parametrized task_state
        return [
            {
                "UpdatedAt": "2026-01-01T00:00:00.000000000Z",
                "Status": {"State": task_state.value},
            }
        ]

    mock_docker.services.list = _filter_services
    mock_docker.tasks.list = _filter_tasks
    mocker.patch(
        "simcore_service_dynamic_scheduler.services.p_scheduler._node_status._docker.get_remote_docker_client",
        return_value=mock_docker,
    )


@pytest.mark.parametrize(
    "task_state, expected_presence", [(ts, _DOCKER_TASK_STATE_TO_SERVICE_STATE[ts]) for ts in list(TaskState)]
)
async def test_get_services_presence(
    mock_docker_client: None,
    task_state: TaskState,
    expected_presence: ComponentPresence,
    app: FastAPI,
    node_id_legacy: NodeID,
    node_id_new_style_one_of_two: NodeID,
    node_id_new_style_two_of_two: NodeID,
):
    assert await get_services_presence(app, node_id_legacy) == ServicesPresence(
        legacy=expected_presence,
    )

    assert await get_services_presence(app, node_id_new_style_one_of_two) == ServicesPresence(
        dy_sidecar=expected_presence,
        dy_proxy=ComponentPresence.ABSENT,
    )

    assert await get_services_presence(app, node_id_new_style_two_of_two) == ServicesPresence(
        dy_sidecar=expected_presence,
        dy_proxy=expected_presence,
    )
