# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

from unittest.mock import AsyncMock

import pytest
import pytest_mock
from faker import Faker
from fastapi import FastAPI
from models_library.generated_models.docker_rest_api import Status1 as ContainerState
from models_library.projects_nodes_io import NodeID
from simcore_service_dynamic_scheduler.services.p_scheduler._node_status._models import ComponentPresence
from simcore_service_dynamic_scheduler.services.p_scheduler._node_status._status_user_services import (
    get_user_services_presence,
)

_A = ComponentPresence.ABSENT
_S = ComponentPresence.STARTING
_R = ComponentPresence.RUNNING
_F = ComponentPresence.FAILED


@pytest.fixture
def node_id(faker: Faker) -> NodeID:
    return faker.uuid4(cast_to=None)


@pytest.fixture
def mocked_app() -> AsyncMock:
    mock = AsyncMock(spec=FastAPI)
    mock.state = AsyncMock()
    return mock


@pytest.fixture
async def mock_containers_docker_inspect(
    mocker: pytest_mock.MockerFixture,
    container_states: list[ContainerState],
) -> None:
    mocker.patch(
        "simcore_service_dynamic_scheduler.services.p_scheduler._node_status._status_user_services.containers_docker_inspect",
        return_value={f"container_{i}": {"State": s.value} for i, s in enumerate(container_states)},
    )


@pytest.mark.parametrize(
    "container_states, expected",
    [
        # --- 0 containers: absent ---
        ([], _A),
        # --- 1 container ---
        ([ContainerState.running], _R),
        ([ContainerState.created], _S),
        ([ContainerState.restarting], _S),
        ([ContainerState.removing], _S),
        ([ContainerState.paused], _F),
        ([ContainerState.exited], _F),
        ([ContainerState.dead], _F),
        # --- 2 containers: worst wins ---
        ([ContainerState.running, ContainerState.running], _R),
        ([ContainerState.running, ContainerState.created], _S),  # starting > running
        ([ContainerState.running, ContainerState.exited], _F),  # failed > running
        ([ContainerState.created, ContainerState.created], _S),
        ([ContainerState.created, ContainerState.dead], _F),  # failed > starting
        # --- 3 containers: worst wins ---
        ([ContainerState.running, ContainerState.running, ContainerState.running], _R),
        ([ContainerState.running, ContainerState.running, ContainerState.created], _S),
        ([ContainerState.running, ContainerState.created, ContainerState.exited], _F),
        ([ContainerState.running, ContainerState.running, ContainerState.paused], _F),
        # --- 4 containers: worst wins ---
        ([ContainerState.running, ContainerState.running, ContainerState.running, ContainerState.running], _R),
        ([ContainerState.running, ContainerState.running, ContainerState.running, ContainerState.created], _S),
        ([ContainerState.running, ContainerState.running, ContainerState.created, ContainerState.restarting], _S),
        ([ContainerState.running, ContainerState.running, ContainerState.running, ContainerState.dead], _F),
        ([ContainerState.running, ContainerState.created, ContainerState.exited, ContainerState.dead], _F),
    ],
)
async def test_get_user_services_presence(
    mock_containers_docker_inspect: None,
    mocked_app: AsyncMock,
    node_id: NodeID,
    expected: ComponentPresence,
):
    assert await get_user_services_presence(mocked_app, node_id) == expected
