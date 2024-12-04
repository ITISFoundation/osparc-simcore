# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name


import pytest
from aioresponses import aioresponses
from faker import Faker
from models_library.projects import ProjectID
from models_library.projects_pipeline import ComputationTask
from models_library.projects_state import RunningState
from models_library.users import UserID
from simcore_service_webserver.director_v2 import api


@pytest.fixture()
async def mocked_director_v2(
    director_v2_service_mock: aioresponses,
) -> aioresponses:
    return director_v2_service_mock


@pytest.fixture
def user_id(faker: Faker) -> UserID:
    return UserID(faker.pyint(min_value=1))


@pytest.fixture
def project_id(faker: Faker) -> ProjectID:
    return ProjectID(faker.uuid4())


async def test_create_pipeline(
    mocked_director_v2,
    client,
    user_id: UserID,
    project_id: ProjectID,
    osparc_product_name: str,
):
    task_out = await api.create_or_update_pipeline(
        client.app, user_id, project_id, osparc_product_name
    )
    assert task_out
    assert isinstance(task_out, dict)
    assert task_out["state"] == RunningState.NOT_STARTED


async def test_get_computation_task(
    mocked_director_v2,
    client,
    user_id: UserID,
    project_id: ProjectID,
):
    task_out = await api.get_computation_task(client.app, user_id, project_id)
    assert task_out
    assert isinstance(task_out, ComputationTask)
    assert task_out.state == RunningState.NOT_STARTED


async def test_delete_pipeline(
    mocked_director_v2, client, user_id: UserID, project_id: ProjectID
):
    await api.delete_pipeline(client.app, user_id, project_id)
