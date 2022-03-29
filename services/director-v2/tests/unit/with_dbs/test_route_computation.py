# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=protected-access
# pylint:disable=no-value-for-parameter
# pylint:disable=too-many-arguments

from typing import Any, Callable, Dict, List

import httpx
import pytest
from faker import Faker
from models_library.projects import ProjectAtDB
from models_library.projects_pipeline import PipelineDetails
from models_library.projects_state import RunningState
from simcore_service_director_v2.models.domains.comp_pipelines import CompPipelineAtDB
from simcore_service_director_v2.models.domains.comp_tasks import CompTaskAtDB
from simcore_service_director_v2.models.schemas.comp_tasks import ComputationTaskGet
from starlette import status

pytest_simcore_core_services_selection = ["postgres"]
pytest_simcore_ops_services_selection = ["adminer"]


@pytest.fixture()
def minimal_configuration(
    mock_env: None,
    postgres_host_config: Dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("DIRECTOR_V2_DYNAMIC_SIDECAR_ENABLED", "false")
    monkeypatch.setenv("DIRECTOR_V2_POSTGRES_ENABLED", "1")


async def test_get_computation_empty_project(
    minimal_configuration: None,
    registered_user: Callable[..., Dict[str, Any]],
    project: Callable[..., ProjectAtDB],
    pipeline: Callable[..., CompPipelineAtDB],
    tasks: Callable[..., List[CompTaskAtDB]],
    faker: Faker,
    async_client: httpx.AsyncClient,
):
    user = registered_user()
    get_computation_url = httpx.URL(
        f"/v2/computations/{faker.uuid4()}?user_id={user['id']}"
    )
    # the project exists but there is no pipeline yet
    response = await async_client.get(get_computation_url)
    assert response.status_code == status.HTTP_404_NOT_FOUND, response.text
    # create the project
    proj = project(user)
    get_computation_url = httpx.URL(
        f"/v2/computations/{proj.uuid}?user_id={user['id']}"
    )
    response = await async_client.get(get_computation_url)
    assert response.status_code == status.HTTP_404_NOT_FOUND, response.text
    # create the pipeline
    project_pipeline = pipeline(project_id=proj.uuid)
    response = await async_client.get(get_computation_url)
    assert response.status_code == status.HTTP_200_OK, response.text
    returned_computation = ComputationTaskGet.parse_obj(response.json())
    assert returned_computation
    assert returned_computation.id == proj.uuid
    assert returned_computation.state == RunningState.UNKNOWN
    assert returned_computation.pipeline_details == PipelineDetails(
        adjacency_list={}, node_states={}
    )
    assert f"{returned_computation.url.path}" == f"{get_computation_url.path}"
    assert returned_computation.stop_url is None
    assert returned_computation.result is None
