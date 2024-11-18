# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=protected-access
# pylint:disable=no-value-for-parameter
# pylint:disable=too-many-arguments

import asyncio
import json
from collections.abc import Awaitable, Callable
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
import pytest
import sqlalchemy as sa
from helpers.shared_comp_utils import (
    assert_and_wait_for_pipeline_status,
    assert_computation_task_out_obj,
)
from models_library.api_schemas_directorv2.comp_tasks import ComputationGet
from models_library.clusters import DEFAULT_CLUSTER_ID, InternalClusterAuthentication
from models_library.projects import ProjectAtDB
from models_library.projects_nodes import NodeState
from models_library.projects_nodes_io import NodeID
from models_library.projects_pipeline import PipelineDetails
from models_library.projects_state import RunningState
from models_library.users import UserID
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict
from pytest_simcore.helpers.postgres_tools import PostgresTestConfig
from pytest_simcore.helpers.typing_env import EnvVarsDict
from settings_library.rabbit import RabbitSettings
from settings_library.redis import RedisSettings
from starlette import status
from starlette.testclient import TestClient
from yarl import URL

pytest_simcore_core_services_selection = [
    "catalog",
    "dask-scheduler",
    "dask-sidecar",
    "director",
    "migration",
    "postgres",
    "rabbit",
    "storage",
    "redis",
]
pytest_simcore_ops_services_selection = ["minio", "adminer"]


@pytest.fixture
def mock_env(
    mock_env: EnvVarsDict,
    minimal_configuration: None,
    monkeypatch: pytest.MonkeyPatch,
    dynamic_sidecar_docker_image_name: str,
    dask_scheduler_service: str,
    dask_scheduler_auth: InternalClusterAuthentication,
) -> None:
    # used by the client fixture
    setenvs_from_dict(
        monkeypatch,
        {
            "COMPUTATIONAL_BACKEND_DASK_CLIENT_ENABLED": "1",
            "COMPUTATIONAL_BACKEND_ENABLED": "1",
            "COMPUTATIONAL_BACKEND_DEFAULT_CLUSTER_URL": dask_scheduler_service,
            "COMPUTATIONAL_BACKEND_DEFAULT_CLUSTER_AUTH": dask_scheduler_auth.model_dump_json(),
            "DYNAMIC_SIDECAR_IMAGE": dynamic_sidecar_docker_image_name,
            "SIMCORE_SERVICES_NETWORK_NAME": "test_swarm_network_name",
            "SWARM_STACK_NAME": "test_mocked_stack_name",
            "TRAEFIK_SIMCORE_ZONE": "test_mocked_simcore_zone",
            "R_CLONE_PROVIDER": "MINIO",
            "SC_BOOT_MODE": "production",
            "DYNAMIC_SIDECAR_PROMETHEUS_SERVICE_LABELS": "{}",
        },
    )


@pytest.fixture
def minimal_configuration(
    sleeper_service: dict[str, str],
    jupyter_service: dict[str, str],
    dask_scheduler_service: str,
    dask_sidecar_service: None,
    postgres_db: sa.engine.Engine,
    postgres_host_config: PostgresTestConfig,
    rabbit_service: RabbitSettings,
    redis_service: RedisSettings,
    simcore_services_ready: None,
    storage_service: URL,
) -> None:
    ...


@pytest.fixture(scope="session")
def fake_workbench_node_states_file(mocks_dir: Path) -> Path:
    file_path = mocks_dir / "fake_workbench_computational_node_states.json"
    assert file_path.exists()
    return file_path


@pytest.fixture(scope="session")
def fake_workbench_computational_pipeline_details(
    fake_workbench_computational_adjacency_file: Path,
    fake_workbench_node_states_file: Path,
) -> PipelineDetails:
    adjacency_list = json.loads(fake_workbench_computational_adjacency_file.read_text())
    node_states = json.loads(fake_workbench_node_states_file.read_text())
    return PipelineDetails.model_validate(
        {"adjacency_list": adjacency_list, "node_states": node_states, "progress": 0}
    )


@pytest.fixture(scope="session")
def fake_workbench_computational_pipeline_details_completed(
    fake_workbench_computational_pipeline_details: PipelineDetails,
) -> PipelineDetails:
    completed_pipeline_details = deepcopy(fake_workbench_computational_pipeline_details)
    for node_state in completed_pipeline_details.node_states.values():
        node_state.modified = False
        node_state.dependencies = set()
        node_state.current_status = RunningState.SUCCESS
        node_state.progress = 1
    completed_pipeline_details.progress = 1
    return completed_pipeline_details


@pytest.fixture(scope="session")
def fake_workbench_computational_pipeline_details_not_started(
    fake_workbench_computational_pipeline_details: PipelineDetails,
) -> PipelineDetails:
    completed_pipeline_details = deepcopy(fake_workbench_computational_pipeline_details)
    for node_state in completed_pipeline_details.node_states.values():
        node_state.modified = True
        node_state.current_status = RunningState.NOT_STARTED
        node_state.progress = None
    return completed_pipeline_details


COMPUTATION_URL: str = "v2/computations"


@pytest.mark.parametrize(
    "body,exp_response",
    [
        (
            {
                "user_id": "some invalid id",
                "project_id": "not a uuid",
                "product_name": "not a product",
            },
            status.HTTP_422_UNPROCESSABLE_ENTITY,
        ),
        (
            {
                "user_id": 2,
                "project_id": "not a uuid",
                "product_name": "not a product",
            },
            status.HTTP_422_UNPROCESSABLE_ENTITY,
        ),
        (
            {
                "user_id": 3,
                "project_id": "16e60a5d-834e-4267-b44d-3af49171bf21",
                "product_name": "not a product",
            },
            status.HTTP_404_NOT_FOUND,
        ),
    ],
)
def test_invalid_computation(
    client: TestClient,
    body: dict,
    exp_response: int,
):
    # create a bunch of invalid stuff
    response = client.post(
        COMPUTATION_URL,
        json=body,
    )
    assert (
        response.status_code == exp_response
    ), f"response code is {response.status_code}, error: {response.text}"


async def test_start_empty_computation_is_refused(
    async_client: httpx.AsyncClient,
    registered_user: Callable,
    project: Callable[..., Awaitable[ProjectAtDB]],
    osparc_product_name: str,
    create_pipeline: Callable[..., Awaitable[ComputationGet]],
):
    user = registered_user()
    empty_project = await project(user)
    with pytest.raises(
        httpx.HTTPStatusError, match=f"{status.HTTP_422_UNPROCESSABLE_ENTITY}"
    ):
        await create_pipeline(
            async_client,
            project=empty_project,
            user_id=user["id"],
            start_pipeline=True,
            product_name=osparc_product_name,
        )


@dataclass
class PartialComputationParams:
    subgraph_elements: list[int]
    exp_pipeline_adj_list: dict[int, list[int]]
    exp_node_states: dict[int, dict[str, Any]]
    exp_node_states_after_run: dict[int, dict[str, Any]]
    exp_pipeline_adj_list_after_force_run: dict[int, list[int]]
    exp_node_states_after_force_run: dict[int, dict[str, Any]]


@pytest.mark.parametrize(
    "params",
    [
        pytest.param(
            PartialComputationParams(
                subgraph_elements=[0, 1],
                exp_pipeline_adj_list={1: []},
                exp_node_states={
                    1: {
                        "modified": True,
                        "dependencies": [],
                        "currentStatus": RunningState.PUBLISHED,
                        "progress": None,
                    },
                    2: {
                        "modified": True,
                        "dependencies": [1],
                        "progress": None,
                    },
                    3: {
                        "modified": True,
                        "dependencies": [],
                        "progress": None,
                    },
                    4: {
                        "modified": True,
                        "dependencies": [2, 3],
                        "progress": None,
                    },
                },
                exp_node_states_after_run={
                    1: {
                        "modified": False,
                        "dependencies": [],
                        "currentStatus": RunningState.SUCCESS,
                        "progress": 1,
                    },
                    2: {
                        "modified": True,
                        "dependencies": [],
                        "progress": None,
                    },
                    3: {
                        "modified": True,
                        "dependencies": [],
                        "progress": None,
                    },
                    4: {
                        "modified": True,
                        "dependencies": [2, 3],
                        "progress": None,
                    },
                },
                exp_pipeline_adj_list_after_force_run={1: []},
                exp_node_states_after_force_run={
                    1: {
                        "modified": False,
                        "dependencies": [],
                        "currentStatus": RunningState.PUBLISHED,
                        "progress": None,
                    },
                    2: {
                        "modified": True,
                        "dependencies": [],
                        "currentStatus": RunningState.NOT_STARTED,
                        "progress": None,
                    },
                    3: {
                        "modified": True,
                        "dependencies": [],
                        "currentStatus": RunningState.NOT_STARTED,
                        "progress": None,
                    },
                    4: {
                        "modified": True,
                        "dependencies": [2, 3],
                        "currentStatus": RunningState.NOT_STARTED,
                        "progress": None,
                    },
                },
            ),
            id="element 0,1",
        ),
        pytest.param(
            PartialComputationParams(
                subgraph_elements=[1, 2, 4],
                exp_pipeline_adj_list={1: [2], 2: [4], 3: [4], 4: []},
                exp_node_states={
                    1: {
                        "modified": True,
                        "dependencies": [],
                        "currentStatus": RunningState.PUBLISHED,
                        "progress": None,
                    },
                    2: {
                        "modified": True,
                        "dependencies": [1],
                        "currentStatus": RunningState.PUBLISHED,
                        "progress": None,
                    },
                    3: {
                        "modified": True,
                        "dependencies": [],
                        "currentStatus": RunningState.PUBLISHED,
                        "progress": None,
                    },
                    4: {
                        "modified": True,
                        "dependencies": [2, 3],
                        "currentStatus": RunningState.PUBLISHED,
                        "progress": None,
                    },
                },
                exp_node_states_after_run={
                    1: {
                        "modified": False,
                        "dependencies": [],
                        "currentStatus": RunningState.SUCCESS,
                        "progress": 1,
                    },
                    2: {
                        "modified": False,
                        "dependencies": [],
                        "currentStatus": RunningState.SUCCESS,
                        "progress": 1,
                    },
                    3: {
                        "modified": False,
                        "dependencies": [],
                        "currentStatus": RunningState.SUCCESS,
                        "progress": 1,
                    },
                    4: {
                        "modified": False,
                        "dependencies": [],
                        "currentStatus": RunningState.SUCCESS,
                        "progress": 1,
                    },
                },
                exp_pipeline_adj_list_after_force_run={1: [2], 2: [4], 4: []},
                exp_node_states_after_force_run={
                    1: {
                        "modified": False,
                        "dependencies": [],
                        "currentStatus": RunningState.PUBLISHED,
                        "progress": None,
                    },
                    2: {
                        "modified": False,
                        "dependencies": [],
                        "currentStatus": RunningState.PUBLISHED,
                        "progress": None,
                    },
                    3: {
                        "modified": False,
                        "dependencies": [],
                        "currentStatus": RunningState.SUCCESS,
                        "progress": 1,
                    },
                    4: {
                        "modified": False,
                        "dependencies": [],
                        "currentStatus": RunningState.PUBLISHED,
                        "progress": None,
                    },
                },
            ),
            id="element 1,2,4",
        ),
    ],
)
async def test_run_partial_computation(
    wait_for_catalog_service: Callable[[UserID, str], Awaitable[None]],
    async_client: httpx.AsyncClient,
    registered_user: Callable,
    project: Callable[..., Awaitable[ProjectAtDB]],
    update_project_workbench_with_comp_tasks: Callable,
    fake_workbench_without_outputs: dict[str, Any],
    params: PartialComputationParams,
    osparc_product_name: str,
    create_pipeline: Callable[..., Awaitable[ComputationGet]],
):
    user = registered_user()
    await wait_for_catalog_service(user["id"], osparc_product_name)
    sleepers_project: ProjectAtDB = await project(
        user, workbench=fake_workbench_without_outputs
    )

    def _convert_to_pipeline_details(
        project: ProjectAtDB,
        exp_pipeline_adj_list: dict[int, list[int]],
        exp_node_states: dict[int, dict[str, Any]],
    ) -> PipelineDetails:
        workbench_node_uuids = list(project.workbench.keys())
        converted_adj_list: dict[NodeID, list[NodeID]] = {}
        for node_key, next_nodes in exp_pipeline_adj_list.items():
            converted_adj_list[NodeID(workbench_node_uuids[node_key])] = [
                NodeID(workbench_node_uuids[n]) for n in next_nodes
            ]
        converted_node_states: dict[NodeID, NodeState] = {
            NodeID(workbench_node_uuids[n]): NodeState(
                modified=s["modified"],
                dependencies={
                    NodeID(workbench_node_uuids[dep_n]) for dep_n in s["dependencies"]
                },
                currentStatus=s.get("currentStatus", RunningState.NOT_STARTED),
                progress=s.get("progress"),
            )
            for n, s in exp_node_states.items()
        }
        pipeline_progress = 0
        for node_id in converted_adj_list:
            node = converted_node_states[node_id]
            pipeline_progress += (node.progress or 0) / len(converted_adj_list)
        return PipelineDetails(
            adjacency_list=converted_adj_list,
            node_states=converted_node_states,
            progress=pipeline_progress,
        )

    # convert the ids to the node uuids from the project
    expected_pipeline_details = _convert_to_pipeline_details(
        sleepers_project, params.exp_pipeline_adj_list, params.exp_node_states
    )

    # send a valid project with sleepers
    task_out = await create_pipeline(
        async_client,
        project=sleepers_project,
        user_id=user["id"],
        start_pipeline=True,
        product_name=osparc_product_name,
        subgraph=[
            str(node_id)
            for index, node_id in enumerate(sleepers_project.workbench)
            if index in params.subgraph_elements
        ],
    )
    # check the contents is correctb
    await assert_computation_task_out_obj(
        task_out,
        project=sleepers_project,
        exp_task_state=RunningState.PUBLISHED,
        exp_pipeline_details=expected_pipeline_details,
        iteration=1,
        cluster_id=DEFAULT_CLUSTER_ID,
    )

    # now wait for the computation to finish
    task_out = await assert_and_wait_for_pipeline_status(
        async_client, task_out.url, user["id"], sleepers_project.uuid
    )
    expected_pipeline_details_after_run = _convert_to_pipeline_details(
        sleepers_project, params.exp_pipeline_adj_list, params.exp_node_states_after_run
    )
    await assert_computation_task_out_obj(
        task_out,
        project=sleepers_project,
        exp_task_state=RunningState.SUCCESS,
        exp_pipeline_details=expected_pipeline_details_after_run,
        iteration=1,
        cluster_id=DEFAULT_CLUSTER_ID,
    )

    # run it a second time. the tasks are all up-to-date, nothing should be run
    # FIXME: currently the webserver is the one updating the projects table so we need to fake this by copying the run_hash
    update_project_workbench_with_comp_tasks(str(sleepers_project.uuid))

    with pytest.raises(
        httpx.HTTPStatusError, match=f"{status.HTTP_422_UNPROCESSABLE_ENTITY}"
    ):
        await create_pipeline(
            async_client,
            project=sleepers_project,
            user_id=user["id"],
            start_pipeline=True,
            product_name=osparc_product_name,
            expected_response_status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            subgraph=[
                str(node_id)
                for index, node_id in enumerate(sleepers_project.workbench)
                if index in params.subgraph_elements
            ],
        )

    # force run it this time.
    # the task are up-to-date but we force run them
    expected_pipeline_details_forced = _convert_to_pipeline_details(
        sleepers_project,
        params.exp_pipeline_adj_list_after_force_run,
        params.exp_node_states_after_force_run,
    )
    task_out = await create_pipeline(
        async_client,
        project=sleepers_project,
        user_id=user["id"],
        start_pipeline=True,
        product_name=osparc_product_name,
        expected_response_status_code=status.HTTP_201_CREATED,
        subgraph=[
            str(node_id)
            for index, node_id in enumerate(sleepers_project.workbench)
            if index in params.subgraph_elements
        ],
        force_restart=True,
    )

    await assert_computation_task_out_obj(
        task_out,
        project=sleepers_project,
        exp_task_state=RunningState.PUBLISHED,
        exp_pipeline_details=expected_pipeline_details_forced,
        iteration=2,
        cluster_id=DEFAULT_CLUSTER_ID,
    )

    # now wait for the computation to finish
    task_out = await assert_and_wait_for_pipeline_status(
        async_client, task_out.url, user["id"], sleepers_project.uuid
    )


async def test_run_computation(
    wait_for_catalog_service: Callable[[UserID, str], Awaitable[None]],
    async_client: httpx.AsyncClient,
    registered_user: Callable,
    project: Callable[..., Awaitable[ProjectAtDB]],
    fake_workbench_without_outputs: dict[str, Any],
    update_project_workbench_with_comp_tasks: Callable,
    fake_workbench_computational_pipeline_details: PipelineDetails,
    fake_workbench_computational_pipeline_details_completed: PipelineDetails,
    osparc_product_name: str,
    create_pipeline: Callable[..., Awaitable[ComputationGet]],
):
    user = registered_user()
    await wait_for_catalog_service(user["id"], osparc_product_name)
    sleepers_project = await project(user, workbench=fake_workbench_without_outputs)
    # send a valid project with sleepers
    task_out = await create_pipeline(
        async_client,
        project=sleepers_project,
        user_id=user["id"],
        start_pipeline=True,
        product_name=osparc_product_name,
        expected_response_status_code=status.HTTP_201_CREATED,
    )

    # check the contents is correct: a pipeline that just started gets PUBLISHED
    await assert_computation_task_out_obj(
        task_out,
        project=sleepers_project,
        exp_task_state=RunningState.PUBLISHED,
        exp_pipeline_details=fake_workbench_computational_pipeline_details,
        iteration=1,
        cluster_id=DEFAULT_CLUSTER_ID,
    )

    # wait for the computation to start
    await assert_and_wait_for_pipeline_status(
        async_client,
        task_out.url,
        user["id"],
        sleepers_project.uuid,
        wait_for_states=[RunningState.STARTED],
    )

    # wait for the computation to finish (either by failing, success or abort)
    task_out = await assert_and_wait_for_pipeline_status(
        async_client, task_out.url, user["id"], sleepers_project.uuid
    )

    await assert_computation_task_out_obj(
        task_out,
        project=sleepers_project,
        exp_task_state=RunningState.SUCCESS,
        exp_pipeline_details=fake_workbench_computational_pipeline_details_completed,
        iteration=1,
        cluster_id=DEFAULT_CLUSTER_ID,
    )

    # NOTE: currently the webserver is the one updating the projects table so we need to fake this by copying the run_hash
    update_project_workbench_with_comp_tasks(str(sleepers_project.uuid))
    # run again should return a 422 cause everything is uptodate
    with pytest.raises(
        httpx.HTTPStatusError, match=f"{status.HTTP_422_UNPROCESSABLE_ENTITY}"
    ):
        await create_pipeline(
            async_client,
            project=sleepers_project,
            user_id=user["id"],
            start_pipeline=True,
            product_name=osparc_product_name,
        )

    # now force run again
    # the task are up-to-date but we force run them
    expected_pipeline_details_forced = deepcopy(
        fake_workbench_computational_pipeline_details_completed
    )
    for node_id, node_data in expected_pipeline_details_forced.node_states.items():
        node_data.current_status = (
            fake_workbench_computational_pipeline_details.node_states[
                node_id
            ].current_status
        )
        node_data.progress = fake_workbench_computational_pipeline_details.node_states[
            node_id
        ].progress
    expected_pipeline_details_forced.progress = 0
    task_out = await create_pipeline(
        async_client,
        project=sleepers_project,
        user_id=user["id"],
        start_pipeline=True,
        product_name=osparc_product_name,
        force_restart=True,
    )
    # check the contents is correct
    await assert_computation_task_out_obj(
        task_out,
        project=sleepers_project,
        exp_task_state=RunningState.PUBLISHED,
        exp_pipeline_details=expected_pipeline_details_forced,  # NOTE: here the pipeline already ran so its states are different
        iteration=2,
        cluster_id=DEFAULT_CLUSTER_ID,
    )

    # wait for the computation to finish
    task_out = await assert_and_wait_for_pipeline_status(
        async_client, task_out.url, user["id"], sleepers_project.uuid
    )
    await assert_computation_task_out_obj(
        task_out,
        project=sleepers_project,
        exp_task_state=RunningState.SUCCESS,
        exp_pipeline_details=fake_workbench_computational_pipeline_details_completed,
        iteration=2,
        cluster_id=DEFAULT_CLUSTER_ID,
    )


async def test_abort_computation(
    async_client: httpx.AsyncClient,
    registered_user: Callable,
    project: Callable[..., Awaitable[ProjectAtDB]],
    fake_workbench_without_outputs: dict[str, Any],
    fake_workbench_computational_pipeline_details: PipelineDetails,
    osparc_product_name: str,
    create_pipeline: Callable[..., Awaitable[ComputationGet]],
):
    user = registered_user()
    # we need long running tasks to ensure cancellation is done properly
    for node in fake_workbench_without_outputs.values():
        if "sleeper" in node["key"]:
            node["inputs"].setdefault("in_2", 120)
            if not isinstance(node["inputs"]["in_2"], dict):
                node["inputs"]["in_2"] = 120
    sleepers_project = await project(user, workbench=fake_workbench_without_outputs)
    # send a valid project with sleepers
    task_out = await create_pipeline(
        async_client,
        project=sleepers_project,
        user_id=user["id"],
        start_pipeline=True,
        product_name=osparc_product_name,
    )

    # check the contents is correctb
    await assert_computation_task_out_obj(
        task_out,
        project=sleepers_project,
        exp_task_state=RunningState.PUBLISHED,
        exp_pipeline_details=fake_workbench_computational_pipeline_details,
        iteration=1,
        cluster_id=DEFAULT_CLUSTER_ID,
    )

    # wait until the pipeline is started
    task_out = await assert_and_wait_for_pipeline_status(
        async_client,
        task_out.url,
        user["id"],
        sleepers_project.uuid,
        wait_for_states=[RunningState.STARTED],
    )
    assert (
        task_out.state == RunningState.STARTED
    ), f"pipeline is not in the expected starting state but in {task_out.state}"
    assert task_out.url.path == f"/v2/computations/{sleepers_project.uuid}"
    assert task_out.stop_url
    assert task_out.stop_url.path == f"/v2/computations/{sleepers_project.uuid}:stop"
    get_computation_state_url = deepcopy(task_out.url)
    # wait a bit till it has some momentum
    await asyncio.sleep(5)

    # now abort the pipeline
    response = await async_client.post(
        f"{task_out.stop_url}", json={"user_id": user["id"]}
    )
    assert (
        response.status_code == status.HTTP_202_ACCEPTED
    ), f"response code is {response.status_code}, error: {response.text}"
    task_out = ComputationGet.model_validate(response.json())
    assert task_out.url.path == f"/v2/computations/{sleepers_project.uuid}:stop"
    assert task_out.stop_url is None

    # check that the pipeline is aborted/stopped
    task_out = await assert_and_wait_for_pipeline_status(
        async_client,
        get_computation_state_url,
        user["id"],
        sleepers_project.uuid,
        wait_for_states=[RunningState.ABORTED],
    )
    assert task_out.state == RunningState.ABORTED
    # FIXME: Here ideally we should connect to the dask scheduler and check
    # that the task is really aborted


async def test_update_and_delete_computation(
    async_client: httpx.AsyncClient,
    registered_user: Callable,
    project: Callable[..., Awaitable[ProjectAtDB]],
    fake_workbench_without_outputs: dict[str, Any],
    fake_workbench_computational_pipeline_details_not_started: PipelineDetails,
    fake_workbench_computational_pipeline_details: PipelineDetails,
    osparc_product_name: str,
    create_pipeline: Callable[..., Awaitable[ComputationGet]],
):
    user = registered_user()
    sleepers_project = await project(user, workbench=fake_workbench_without_outputs)
    # send a valid project with sleepers
    task_out = await create_pipeline(
        async_client,
        project=sleepers_project,
        user_id=user["id"],
        start_pipeline=False,
        product_name=osparc_product_name,
    )

    # check the contents is correctb
    await assert_computation_task_out_obj(
        task_out,
        project=sleepers_project,
        exp_task_state=RunningState.NOT_STARTED,
        exp_pipeline_details=fake_workbench_computational_pipeline_details_not_started,
        iteration=None,
        cluster_id=None,
    )

    # update the pipeline
    task_out = await create_pipeline(
        async_client,
        project=sleepers_project,
        user_id=user["id"],
        start_pipeline=False,
        product_name=osparc_product_name,
    )

    # check the contents is correctb
    await assert_computation_task_out_obj(
        task_out,
        project=sleepers_project,
        exp_task_state=RunningState.NOT_STARTED,
        exp_pipeline_details=fake_workbench_computational_pipeline_details_not_started,
        iteration=None,
        cluster_id=None,
    )

    # update the pipeline
    task_out = await create_pipeline(
        async_client,
        project=sleepers_project,
        user_id=user["id"],
        start_pipeline=False,
        product_name=osparc_product_name,
    )

    # check the contents is correctb
    await assert_computation_task_out_obj(
        task_out,
        project=sleepers_project,
        exp_task_state=RunningState.NOT_STARTED,
        exp_pipeline_details=fake_workbench_computational_pipeline_details_not_started,
        iteration=None,
        cluster_id=None,
    )

    # start it now
    task_out = await create_pipeline(
        async_client,
        project=sleepers_project,
        user_id=user["id"],
        start_pipeline=True,
        product_name=osparc_product_name,
    )
    # check the contents is correctb
    await assert_computation_task_out_obj(
        task_out,
        project=sleepers_project,
        exp_task_state=RunningState.PUBLISHED,
        exp_pipeline_details=fake_workbench_computational_pipeline_details,
        iteration=1,
        cluster_id=DEFAULT_CLUSTER_ID,
    )

    # wait until the pipeline is started
    task_out = await assert_and_wait_for_pipeline_status(
        async_client,
        task_out.url,
        user["id"],
        sleepers_project.uuid,
        wait_for_states=[RunningState.STARTED],
    )
    assert (
        task_out.state == RunningState.STARTED
    ), f"pipeline is not in the expected starting state but in {task_out.state}"

    # now try to update the pipeline, is expected to be forbidden
    with pytest.raises(httpx.HTTPStatusError, match=f"{status.HTTP_409_CONFLICT}"):
        await create_pipeline(
            async_client,
            project=sleepers_project,
            user_id=user["id"],
            start_pipeline=False,
            product_name=osparc_product_name,
        )

    # try to delete the pipeline, is expected to be forbidden if force parameter is false (default)
    response = await async_client.request(
        "DELETE", f"{task_out.url}", json={"user_id": user["id"]}
    )
    assert (
        response.status_code == status.HTTP_403_FORBIDDEN
    ), f"response code is {response.status_code}, error: {response.text}"

    # try again with force=True this should abort and delete the pipeline
    response = await async_client.request(
        "DELETE", f"{task_out.url}", json={"user_id": user["id"], "force": True}
    )
    assert (
        response.status_code == status.HTTP_204_NO_CONTENT
    ), f"response code is {response.status_code}, error: {response.text}"


async def test_pipeline_with_no_computational_services_still_create_correct_comp_tasks_in_db(
    async_client: httpx.AsyncClient,
    registered_user: Callable,
    project: Callable[..., Awaitable[ProjectAtDB]],
    jupyter_service: dict[str, Any],
    osparc_product_name: str,
    create_pipeline: Callable[..., Awaitable[ComputationGet]],
):
    user = registered_user()
    # create a workbench with just a dynamic service
    project_with_dynamic_node = await project(
        user,
        workbench={
            "39e92f80-9286-5612-85d1-639fa47ec57d": {
                "key": jupyter_service["image"]["name"],
                "version": jupyter_service["image"]["tag"],
                "label": "my sole dynamic service",
            }
        },
    )

    # this pipeline is not runnable as there are no computational services
    with pytest.raises(
        httpx.HTTPStatusError, match=f"{status.HTTP_422_UNPROCESSABLE_ENTITY}"
    ):
        await create_pipeline(
            async_client,
            project=project_with_dynamic_node,
            user_id=user["id"],
            start_pipeline=True,
            product_name=osparc_product_name,
        )

    # still this pipeline shall be createable if we do not want to start it
    await create_pipeline(
        async_client,
        project=project_with_dynamic_node,
        user_id=user["id"],
        start_pipeline=False,
        product_name=osparc_product_name,
    )


async def test_pipeline_with_control_loop_made_of_dynamic_services_is_allowed(
    client: TestClient,
    registered_user: Callable,
    project: Callable[..., Awaitable[ProjectAtDB]],
    jupyter_service: dict[str, Any],
    osparc_product_name: str,
):
    user = registered_user()
    # create a workbench with just 2 dynamic service in a cycle
    project_with_dynamic_node = await project(
        user,
        workbench={
            "39e92f80-9286-5612-85d1-639fa47ec57d": {
                "key": jupyter_service["image"]["name"],
                "version": jupyter_service["image"]["tag"],
                "label": "the controller",
                "inputs": {
                    "input_1": {
                        "nodeUuid": "09b92a4b-8bf4-49ad-82d3-1855c5a4957a",
                        "output": "output_1",
                    }
                },
                "inputNodes": ["09b92a4b-8bf4-49ad-82d3-1855c5a4957a"],
            },
            "09b92a4b-8bf4-49ad-82d3-1855c5a4957a": {
                "key": jupyter_service["image"]["name"],
                "version": jupyter_service["image"]["tag"],
                "label": "the model",
                "inputs": {
                    "input_1": {
                        "nodeUuid": "39e92f80-9286-5612-85d1-639fa47ec57d",
                        "output": "output_1",
                    }
                },
                "inputNodes": ["39e92f80-9286-5612-85d1-639fa47ec57d"],
            },
        },
    )

    # this pipeline is not runnable as there are no computational services
    response = client.post(
        COMPUTATION_URL,
        json={
            "user_id": user["id"],
            "project_id": str(project_with_dynamic_node.uuid),
            "start_pipeline": True,
            "product_name": osparc_product_name,
        },
    )
    assert (
        response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    ), f"response code is {response.status_code}, error: {response.text}"

    # still this pipeline shall be createable if we do not want to start it
    response = client.post(
        COMPUTATION_URL,
        json={
            "user_id": user["id"],
            "project_id": str(project_with_dynamic_node.uuid),
            "start_pipeline": False,
            "product_name": osparc_product_name,
        },
    )
    assert (
        response.status_code == status.HTTP_201_CREATED
    ), f"response code is {response.status_code}, error: {response.text}"


async def test_pipeline_with_cycle_containing_a_computational_service_is_forbidden(
    client: TestClient,
    registered_user: Callable,
    project: Callable[..., Awaitable[ProjectAtDB]],
    sleeper_service: dict[str, Any],
    jupyter_service: dict[str, Any],
    osparc_product_name: str,
):
    user = registered_user()
    # create a workbench with just 2 dynamic service in a cycle
    project_with_cycly_and_comp_service = await project(
        user,
        workbench={
            "39e92f80-9286-5612-85d1-639fa47ec57d": {
                "key": jupyter_service["image"]["name"],
                "version": jupyter_service["image"]["tag"],
                "label": "the controller",
                "inputs": {
                    "input_1": {
                        "nodeUuid": "09b92a4b-8bf4-49ad-82d3-1855c5a4957c",
                        "output": "output_1",
                    }
                },
                "inputNodes": ["09b92a4b-8bf4-49ad-82d3-1855c5a4957c"],
            },
            "09b92a4b-8bf4-49ad-82d3-1855c5a4957a": {
                "key": jupyter_service["image"]["name"],
                "version": jupyter_service["image"]["tag"],
                "label": "the model",
                "inputs": {
                    "input_1": {
                        "nodeUuid": "39e92f80-9286-5612-85d1-639fa47ec57d",
                        "output": "output_1",
                    }
                },
                "inputNodes": ["39e92f80-9286-5612-85d1-639fa47ec57d"],
            },
            "09b92a4b-8bf4-49ad-82d3-1855c5a4957c": {
                "key": sleeper_service["image"]["name"],
                "version": sleeper_service["image"]["tag"],
                "label": "the computational service",
                "inputs": {
                    "input_1": {
                        "nodeUuid": "09b92a4b-8bf4-49ad-82d3-1855c5a4957a",
                        "output": "output_1",
                    }
                },
                "inputNodes": ["09b92a4b-8bf4-49ad-82d3-1855c5a4957a"],
            },
        },
    )

    # this pipeline is not runnable as there are no computational services and it contains a cycle
    response = client.post(
        COMPUTATION_URL,
        json={
            "user_id": user["id"],
            "project_id": str(project_with_cycly_and_comp_service.uuid),
            "start_pipeline": True,
            "product_name": osparc_product_name,
        },
    )
    assert (
        response.status_code == status.HTTP_409_CONFLICT
    ), f"response code is {response.status_code}, error: {response.text}"

    # still this pipeline shall be createable if we do not want to start it
    response = client.post(
        COMPUTATION_URL,
        json={
            "user_id": user["id"],
            "project_id": str(project_with_cycly_and_comp_service.uuid),
            "start_pipeline": False,
            "product_name": osparc_product_name,
        },
    )
    assert (
        response.status_code == status.HTTP_201_CREATED
    ), f"response code is {response.status_code}, error: {response.text}"


async def test_burst_create_computations(
    async_client: httpx.AsyncClient,
    registered_user: Callable,
    project: Callable[..., Awaitable[ProjectAtDB]],
    fake_workbench_without_outputs: dict[str, Any],
    update_project_workbench_with_comp_tasks: Callable,
    fake_workbench_computational_pipeline_details: PipelineDetails,
    fake_workbench_computational_pipeline_details_completed: PipelineDetails,
    osparc_product_name: str,
    create_pipeline: Callable[..., Awaitable[ComputationGet]],
):
    user = registered_user()
    sleepers_project = await project(user, workbench=fake_workbench_without_outputs)
    sleepers_project2 = await project(user, workbench=fake_workbench_without_outputs)

    NUMBER_OF_CALLS = 4

    # creating 4 pipelines without starting should return 4 times 201
    # the second pipeline should also return a 201
    responses = await asyncio.gather(
        *(
            [
                create_pipeline(
                    async_client,
                    project=sleepers_project,
                    user_id=user["id"],
                    product_name=osparc_product_name,
                    start_pipeline=False,
                )
                for _ in range(NUMBER_OF_CALLS)
            ]
            + [
                create_pipeline(
                    async_client,
                    project=sleepers_project2,
                    user_id=user["id"],
                    product_name=osparc_product_name,
                    start_pipeline=False,
                )
            ]
        )
    )
    assert all(isinstance(r, ComputationGet) for r in responses)

    # starting 4 pipelines should return 1 time 201 and 3 times 403
    # the second pipeline should return a 201
    responses = await asyncio.gather(
        *(
            [
                create_pipeline(
                    async_client,
                    project=sleepers_project,
                    user_id=user["id"],
                    product_name=osparc_product_name,
                    start_pipeline=True,
                )
                for _ in range(NUMBER_OF_CALLS)
            ]
            + [
                create_pipeline(
                    async_client,
                    project=sleepers_project2,
                    user_id=user["id"],
                    product_name=osparc_product_name,
                    start_pipeline=False,
                )
            ]
        ),
        return_exceptions=True,
    )
    created_tasks = [r for r in responses if isinstance(r, ComputationGet)]
    failed_tasks = [r for r in responses if isinstance(r, httpx.HTTPStatusError)]

    assert len(created_tasks) == 2
    assert len(failed_tasks) == (NUMBER_OF_CALLS - 1)
