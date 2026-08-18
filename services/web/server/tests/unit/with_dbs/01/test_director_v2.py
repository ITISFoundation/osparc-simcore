# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

import pytest
from aiohttp.test_utils import TestClient
from aioresponses import aioresponses
from faker import Faker
from models_library.projects import ProjectID
from models_library.projects_pipeline import ComputationTask
from models_library.projects_state import RunningState
from models_library.users import UserID
from pytest_mock import MockerFixture
from servicelib.rabbitmq.rpc_interfaces.director_v2.errors import (
    ComputationStatesRetrievalError,
)
from simcore_service_webserver.director_v2 import director_v2_service
from simcore_service_webserver.director_v2.exceptions import (
    DirectorV2StateRetrievalError,
)


@pytest.fixture()
async def mocked_director_v2(
    director_v2_service_mock: aioresponses,
) -> aioresponses:
    return director_v2_service_mock


@pytest.fixture
def project_id(faker: Faker) -> ProjectID:
    return ProjectID(faker.uuid4())


async def test_create_pipeline(
    mocked_director_v2: aioresponses,
    client: TestClient,
    user_id: UserID,
    project_id: ProjectID,
    osparc_product_name: str,
    osparc_product_api_base_url: str,
):
    assert client.app

    task_out = await director_v2_service.create_or_update_pipeline(
        client.app,
        user_id,
        project_id,
        osparc_product_name,
        osparc_product_api_base_url,
    )
    assert task_out
    assert isinstance(task_out, dict)
    assert task_out["state"] == RunningState.NOT_STARTED


async def test_get_computation_task(
    mocked_director_v2: aioresponses,
    client: TestClient,
    user_id: UserID,
    project_id: ProjectID,
):
    assert client.app

    task_out = await director_v2_service.get_computation_task(client.app, user_id, project_id)
    assert task_out
    assert isinstance(task_out, ComputationTask)
    assert task_out.state == RunningState.NOT_STARTED


async def test_list_computations_latest_states_raises_domain_error_on_rpc_failure(
    client: TestClient,
    mocker: MockerFixture,
    project_id: ProjectID,
):
    assert client.app
    mocker.patch(
        "simcore_service_webserver.director_v2._director_v2_service.computations.list_computations_latest_states",
        side_effect=ComputationStatesRetrievalError,
    )

    with pytest.raises(DirectorV2StateRetrievalError):
        await director_v2_service.list_computations_latest_states(
            client.app,
            project_ids=[project_id],
        )


async def test_delete_pipeline(
    mocked_director_v2: aioresponses,
    client: TestClient,
    user_id: UserID,
    project_id: ProjectID,
):
    assert client.app
    await director_v2_service.delete_pipeline(client.app, user_id, project_id)
