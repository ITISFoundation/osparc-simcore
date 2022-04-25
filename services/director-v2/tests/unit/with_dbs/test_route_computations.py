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
from models_library.clusters import DEFAULT_CLUSTER_ID
from models_library.projects import ProjectAtDB
from models_library.projects_nodes import NodeID, NodeState
from models_library.projects_pipeline import PipelineDetails
from models_library.projects_state import RunningState
from pydantic import AnyHttpUrl, parse_obj_as
from simcore_postgres_database.models.comp_pipeline import StateType
from simcore_postgres_database.models.comp_tasks import NodeClass
from simcore_service_director_v2.models.domains.comp_pipelines import CompPipelineAtDB
from simcore_service_director_v2.models.domains.comp_runs import CompRunsAtDB
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
    monkeypatch.setenv("R_CLONE_PROVIDER", "MINIO")
    monkeypatch.setenv("S3_ENDPOINT", "endpoint")
    monkeypatch.setenv("S3_ACCESS_KEY", "access_key")
    monkeypatch.setenv("S3_SECRET_KEY", "secret_key")
    monkeypatch.setenv("S3_BUCKET_NAME", "bucket_name")
    monkeypatch.setenv("S3_SECURE", "false")
    monkeypatch.setenv("R_CLONE_STORAGE_ENDPOINT", "storage_endpoint")


async def test_get_computation_from_empty_project(
    minimal_configuration: None,
    fake_workbench_without_outputs: Dict[str, Any],
    fake_workbench_adjacency: Dict[str, Any],
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
    proj = project(user, workbench=fake_workbench_without_outputs)
    get_computation_url = httpx.URL(
        f"/v2/computations/{proj.uuid}?user_id={user['id']}"
    )
    response = await async_client.get(get_computation_url)
    assert response.status_code == status.HTTP_404_NOT_FOUND, response.text
    # create an empty pipeline
    pipeline(
        project_id=proj.uuid,
    )
    response = await async_client.get(get_computation_url)
    assert response.status_code == status.HTTP_200_OK, response.text
    returned_computation = ComputationTaskGet.parse_obj(response.json())
    assert returned_computation
    expected_computation = ComputationTaskGet(
        id=proj.uuid,
        state=RunningState.UNKNOWN,
        pipeline_details=PipelineDetails(adjacency_list={}, node_states={}),
        url=parse_obj_as(
            AnyHttpUrl, f"{async_client.base_url.join(get_computation_url)}"
        ),
        stop_url=None,
        result=None,
        iteration=None,
        cluster_id=None,
    )
    assert returned_computation.dict() == expected_computation.dict()


async def test_get_computation_from_not_started_computation_task(
    minimal_configuration: None,
    fake_workbench_without_outputs: Dict[str, Any],
    fake_workbench_adjacency: Dict[str, Any],
    registered_user: Callable[..., Dict[str, Any]],
    project: Callable[..., ProjectAtDB],
    pipeline: Callable[..., CompPipelineAtDB],
    tasks: Callable[..., List[CompTaskAtDB]],
    faker: Faker,
    async_client: httpx.AsyncClient,
):
    user = registered_user()
    proj = project(user, workbench=fake_workbench_without_outputs)
    get_computation_url = httpx.URL(
        f"/v2/computations/{proj.uuid}?user_id={user['id']}"
    )
    pipeline(
        project_id=proj.uuid,
        dag_adjacency_list=fake_workbench_adjacency,
    )
    # create no task this should trigger an exception
    response = await async_client.get(get_computation_url)
    assert response.status_code == status.HTTP_409_CONFLICT, response.text

    # now create the expected tasks and the state is good again
    comp_tasks = tasks(user=user, project=proj)
    response = await async_client.get(get_computation_url)
    assert response.status_code == status.HTTP_200_OK, response.text
    returned_computation = ComputationTaskGet.parse_obj(response.json())
    assert returned_computation
    expected_computation = ComputationTaskGet(
        id=proj.uuid,
        state=RunningState.NOT_STARTED,
        pipeline_details=PipelineDetails(
            adjacency_list=parse_obj_as(
                Dict[NodeID, List[NodeID]], fake_workbench_adjacency
            ),
            node_states={
                t.node_id: NodeState(
                    modified=True,
                    currentStatus=RunningState.NOT_STARTED,
                    dependencies={
                        NodeID(node)
                        for node, next_nodes in fake_workbench_adjacency.items()
                        if f"{t.node_id}" in next_nodes
                    },
                )
                for t in comp_tasks
                if t.node_class == NodeClass.COMPUTATIONAL
            },
        ),
        url=parse_obj_as(
            AnyHttpUrl, f"{async_client.base_url.join(get_computation_url)}"
        ),
        stop_url=None,
        result=None,
        iteration=None,
        cluster_id=None,
    )

    assert returned_computation.dict() == expected_computation.dict()


async def test_get_computation_from_published_computation_task(
    minimal_configuration: None,
    fake_workbench_without_outputs: Dict[str, Any],
    fake_workbench_adjacency: Dict[str, Any],
    registered_user: Callable[..., Dict[str, Any]],
    project: Callable[..., ProjectAtDB],
    pipeline: Callable[..., CompPipelineAtDB],
    tasks: Callable[..., List[CompTaskAtDB]],
    runs: Callable[..., CompRunsAtDB],
    faker: Faker,
    async_client: httpx.AsyncClient,
):
    user = registered_user()
    proj = project(user, workbench=fake_workbench_without_outputs)
    pipeline(
        project_id=proj.uuid,
        dag_adjacency_list=fake_workbench_adjacency,
    )
    comp_tasks = tasks(user=user, project=proj, state=StateType.PUBLISHED)
    comp_runs = runs(user=user, project=proj, result=StateType.PUBLISHED)
    get_computation_url = httpx.URL(
        f"/v2/computations/{proj.uuid}?user_id={user['id']}"
    )
    response = await async_client.get(get_computation_url)
    assert response.status_code == status.HTTP_200_OK, response.text
    returned_computation = ComputationTaskGet.parse_obj(response.json())
    assert returned_computation
    expected_stop_url = async_client.base_url.join(
        f"/v2/computations/{proj.uuid}:stop?user_id={user['id']}"
    )
    expected_computation = ComputationTaskGet(
        id=proj.uuid,
        state=RunningState.PUBLISHED,
        pipeline_details=PipelineDetails(
            adjacency_list=parse_obj_as(
                Dict[NodeID, List[NodeID]], fake_workbench_adjacency
            ),
            node_states={
                t.node_id: NodeState(
                    modified=True,
                    currentStatus=RunningState.PUBLISHED,
                    dependencies={
                        NodeID(node)
                        for node, next_nodes in fake_workbench_adjacency.items()
                        if f"{t.node_id}" in next_nodes
                    },
                )
                for t in comp_tasks
                if t.node_class == NodeClass.COMPUTATIONAL
            },
        ),
        url=parse_obj_as(
            AnyHttpUrl, f"{async_client.base_url.join(get_computation_url)}"
        ),
        stop_url=parse_obj_as(AnyHttpUrl, f"{expected_stop_url}"),
        result=None,
        iteration=1,
        cluster_id=DEFAULT_CLUSTER_ID,
    )

    assert returned_computation.dict() == expected_computation.dict()
