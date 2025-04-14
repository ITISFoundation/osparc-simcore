# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

import pytest
from aiohttp.test_utils import TestClient
from aioresponses import aioresponses
from models_library.projects import ProjectID
from models_library.projects_pipeline import ComputationTask
from models_library.projects_state import RunningState
from models_library.users import UserID
from simcore_service_webserver.director_v2 import director_v2_service


@pytest.fixture()
async def mocked_director_v2(
    director_v2_service_mock: aioresponses,
) -> aioresponses:
    return director_v2_service_mock


async def test_create_pipeline(
    mocked_director_v2: aioresponses,
    client: TestClient,
    user_id: UserID,
    project_id: ProjectID,
    osparc_product_name: str,
):
    assert client.app

    task_out = await director_v2_service.create_or_update_pipeline(
        client.app, user_id, project_id, osparc_product_name
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

    task_out = await director_v2_service.get_computation_task(
        client.app, user_id, project_id
    )
    assert task_out
    assert isinstance(task_out, ComputationTask)
    assert task_out.state == RunningState.NOT_STARTED


async def test_delete_pipeline(
    mocked_director_v2: aioresponses,
    client: TestClient,
    user_id: UserID,
    project_id: ProjectID,
):
    assert client.app
    await director_v2_service.delete_pipeline(client.app, user_id, project_id)
