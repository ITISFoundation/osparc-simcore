# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=protected-access
# pylint:disable=no-value-for-parameter
# pylint:disable=too-many-arguments

import asyncio
import json
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List

import pytest
import sqlalchemy as sa
from _pytest.monkeypatch import MonkeyPatch
from httpx import AsyncClient
from models_library.projects import ProjectAtDB
from models_library.projects_nodes import NodeState
from models_library.projects_nodes_io import NodeID
from models_library.projects_pipeline import PipelineDetails
from models_library.projects_state import RunningState
from models_library.settings.rabbit import RabbitConfig
from models_library.settings.redis import RedisConfig
from pydantic.types import PositiveInt
from shared_comp_utils import (
    COMPUTATION_URL,
    assert_computation_task_out_obj,
    assert_pipeline_status,
    create_pipeline,
)
from simcore_sdk.node_ports_common import config as node_ports_config
from simcore_service_director_v2.models.schemas.comp_tasks import ComputationTaskOut
from starlette import status
from starlette.testclient import TestClient
from yarl import URL

pytest_simcore_core_services_selection = [
    "dask-scheduler",
    "dask-sidecar",
    "director",
    "migration",
    "postgres",
    "rabbit",
    "redis",
    "storage",
]
pytest_simcore_ops_services_selection = ["minio", "adminer", "flower"]


# FIXTURES ---------------------------------------


@pytest.fixture(scope="function", params=["dask"])
def mock_env(monkeypatch: MonkeyPatch, request) -> None:
    # used by the client fixture
    monkeypatch.setenv("DYNAMIC_SIDECAR_IMAGE", "itisfoundation/dynamic-sidecar:MOCKED")

    monkeypatch.setenv(
        "DIRECTOR_V2_DASK_CLIENT_ENABLED",
        "1" if request.param == "dask" else "0",
    )
    monkeypatch.setenv(
        "DIRECTOR_V2_DASK_SCHEDULER_ENABLED",
        "1" if request.param == "dask" else "0",
    )
    monkeypatch.setenv(
        "DIRECTOR_V2_CELERY_SCHEDULER_ENABLED",
        "1" if request.param == "celery" else "0",
    )
    monkeypatch.setenv("DIRECTOR_V2_TRACING", "null")
    monkeypatch.setenv("SIMCORE_SERVICES_NETWORK_NAME", "test_swarm_network_name")
    monkeypatch.setenv("TRAEFIK_SIMCORE_ZONE", "test_mocked_simcore_zone")
    monkeypatch.setenv("SWARM_STACK_NAME", "test_mocked_stack_name")


@pytest.fixture()
def minimal_configuration(
    sleeper_service: Dict[str, str],
    jupyter_service: Dict[str, str],
    dask_scheduler_service: None,
    dask_sidecar_service: None,
    redis_service: RedisConfig,
    postgres_db: sa.engine.Engine,
    postgres_host_config: Dict[str, str],
    rabbit_service: RabbitConfig,
    simcore_services_ready: None,
    storage_service: URL,
    mocker,
) -> None:
    node_ports_config.STORAGE_ENDPOINT = (
        f"{storage_service.host}:{storage_service.port}"
    )


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
    return PipelineDetails.parse_obj(
        {"adjacency_list": adjacency_list, "node_states": node_states}
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
    return completed_pipeline_details


@pytest.fixture(scope="session")
def fake_workbench_computational_pipeline_details_not_started(
    fake_workbench_computational_pipeline_details: PipelineDetails,
) -> PipelineDetails:
    completed_pipeline_details = deepcopy(fake_workbench_computational_pipeline_details)
    for node_state in completed_pipeline_details.node_states.values():
        node_state.modified = True
        node_state.current_status = RunningState.NOT_STARTED
    return completed_pipeline_details


# TESTS ---------------------------------------


@pytest.mark.parametrize(
    "body,exp_response",
    [
        (
            {"user_id": "some invalid id", "project_id": "not a uuid"},
            status.HTTP_422_UNPROCESSABLE_ENTITY,
        ),
        (
            {"user_id": 2, "project_id": "not a uuid"},
            status.HTTP_422_UNPROCESSABLE_ENTITY,
        ),
        (
            {"user_id": 3, "project_id": "16e60a5d-834e-4267-b44d-3af49171bf21"},
            status.HTTP_404_NOT_FOUND,
        ),
    ],
)
def test_invalid_computation(
    minimal_configuration: None,
    client: TestClient,
    body: Dict,
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


def test_start_empty_computation(
    minimal_configuration: None,
    client: TestClient,
    user_id: PositiveInt,
    project: Callable,
):
    # send an empty project to process
    empty_project = project()
    create_pipeline(
        client,
        project=empty_project,
        user_id=user_id,
        start_pipeline=True,
        expected_response_status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
    )


@dataclass
class PartialComputationParams:
    subgraph_elements: List[int]
    exp_pipeline_adj_list: Dict[int, List[int]]
    exp_node_states: Dict[int, Dict[str, Any]]
    exp_node_states_after_run: Dict[int, Dict[str, Any]]
    exp_pipeline_adj_list_after_force_run: Dict[int, List[int]]
    exp_node_states_after_force_run: Dict[int, Dict[str, Any]]


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
                    },
                    2: {
                        "modified": True,
                        "dependencies": [1],
                    },
                    3: {
                        "modified": True,
                        "dependencies": [],
                    },
                    4: {
                        "modified": True,
                        "dependencies": [2, 3],
                    },
                },
                exp_node_states_after_run={
                    1: {
                        "modified": False,
                        "dependencies": [],
                        "currentStatus": RunningState.SUCCESS,
                    },
                    2: {
                        "modified": True,
                        "dependencies": [],
                    },
                    3: {
                        "modified": True,
                        "dependencies": [],
                    },
                    4: {
                        "modified": True,
                        "dependencies": [2, 3],
                    },
                },
                exp_pipeline_adj_list_after_force_run={1: []},
                exp_node_states_after_force_run={
                    1: {
                        "modified": False,
                        "dependencies": [],
                        "currentStatus": RunningState.PUBLISHED,
                    },
                    2: {
                        "modified": True,
                        "dependencies": [],
                        "currentStatus": RunningState.NOT_STARTED,
                    },
                    3: {
                        "modified": True,
                        "dependencies": [],
                        "currentStatus": RunningState.NOT_STARTED,
                    },
                    4: {
                        "modified": True,
                        "dependencies": [2, 3],
                        "currentStatus": RunningState.NOT_STARTED,
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
                    },
                    2: {
                        "modified": True,
                        "dependencies": [1],
                        "currentStatus": RunningState.PUBLISHED,
                    },
                    3: {
                        "modified": True,
                        "dependencies": [],
                        "currentStatus": RunningState.PUBLISHED,
                    },
                    4: {
                        "modified": True,
                        "dependencies": [2, 3],
                        "currentStatus": RunningState.PUBLISHED,
                    },
                },
                exp_node_states_after_run={
                    1: {
                        "modified": False,
                        "dependencies": [],
                        "currentStatus": RunningState.SUCCESS,
                    },
                    2: {
                        "modified": False,
                        "dependencies": [],
                        "currentStatus": RunningState.SUCCESS,
                    },
                    3: {
                        "modified": False,
                        "dependencies": [],
                        "currentStatus": RunningState.SUCCESS,
                    },
                    4: {
                        "modified": False,
                        "dependencies": [],
                        "currentStatus": RunningState.SUCCESS,
                    },
                },
                exp_pipeline_adj_list_after_force_run={1: [2], 2: [4], 4: []},
                exp_node_states_after_force_run={
                    1: {
                        "modified": False,
                        "dependencies": [],
                        "currentStatus": RunningState.PUBLISHED,
                    },
                    2: {
                        "modified": False,
                        "dependencies": [],
                        "currentStatus": RunningState.PUBLISHED,
                    },
                    3: {
                        "modified": False,
                        "dependencies": [],
                        "currentStatus": RunningState.SUCCESS,
                    },
                    4: {
                        "modified": False,
                        "dependencies": [],
                        "currentStatus": RunningState.PUBLISHED,
                    },
                },
            ),
            id="element 1,2,4",
        ),
    ],
)
async def test_run_partial_computation(
    minimal_configuration: None,
    client: TestClient,
    user_id: PositiveInt,
    project: Callable,
    update_project_workbench_with_comp_tasks: Callable,
    fake_workbench_without_outputs: Dict[str, Any],
    params: PartialComputationParams,
):
    sleepers_project: ProjectAtDB = project(workbench=fake_workbench_without_outputs)

    def _convert_to_pipeline_details(
        project: ProjectAtDB,
        exp_pipeline_adj_list: Dict[int, List[int]],
        exp_node_states: Dict[int, Dict[str, Any]],
    ) -> PipelineDetails:
        workbench_node_uuids = list(project.workbench.keys())
        converted_adj_list: Dict[NodeID, List[NodeID]] = {}
        for node_key, next_nodes in exp_pipeline_adj_list.items():
            converted_adj_list[NodeID(workbench_node_uuids[node_key])] = [
                NodeID(workbench_node_uuids[n]) for n in next_nodes
            ]
        converted_node_states: Dict[NodeID, NodeState] = {
            NodeID(workbench_node_uuids[n]): NodeState(
                modified=s["modified"],
                dependencies={
                    workbench_node_uuids[dep_n] for dep_n in s["dependencies"]
                },
                currentStatus=s.get("currentStatus", RunningState.NOT_STARTED),
            )
            for n, s in exp_node_states.items()
        }
        return PipelineDetails(
            adjacency_list=converted_adj_list, node_states=converted_node_states
        )

    # convert the ids to the node uuids from the project
    expected_pipeline_details = _convert_to_pipeline_details(
        sleepers_project, params.exp_pipeline_adj_list, params.exp_node_states
    )

    # send a valid project with sleepers
    response = create_pipeline(
        client,
        project=sleepers_project,
        user_id=user_id,
        start_pipeline=True,
        expected_response_status_code=status.HTTP_201_CREATED,
        subgraph=[
            str(node_id)
            for index, node_id in enumerate(sleepers_project.workbench)
            if index in params.subgraph_elements
        ],
    )
    task_out = ComputationTaskOut.parse_obj(response.json())
    # check the contents is correctb
    assert_computation_task_out_obj(
        client,
        task_out,
        project=sleepers_project,
        exp_task_state=RunningState.PUBLISHED,
        exp_pipeline_details=expected_pipeline_details,
    )

    # now wait for the computation to finish
    task_out = await assert_pipeline_status(
        client, task_out.url, user_id, sleepers_project.uuid
    )
    expected_pipeline_details_after_run = _convert_to_pipeline_details(
        sleepers_project, params.exp_pipeline_adj_list, params.exp_node_states_after_run
    )
    assert_computation_task_out_obj(
        client,
        task_out,
        project=sleepers_project,
        exp_task_state=RunningState.SUCCESS,
        exp_pipeline_details=expected_pipeline_details_after_run,
    )

    # run it a second time. the tasks are all up-to-date, nothing should be run
    # FIXME: currently the webserver is the one updating the projects table so we need to fake this by copying the run_hash
    update_project_workbench_with_comp_tasks(str(sleepers_project.uuid))

    response = create_pipeline(
        client,
        project=sleepers_project,
        user_id=user_id,
        start_pipeline=True,
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
    response = create_pipeline(
        client,
        project=sleepers_project,
        user_id=user_id,
        start_pipeline=True,
        expected_response_status_code=status.HTTP_201_CREATED,
        subgraph=[
            str(node_id)
            for index, node_id in enumerate(sleepers_project.workbench)
            if index in params.subgraph_elements
        ],
        force_restart=True,
    )
    task_out = ComputationTaskOut.parse_obj(response.json())

    assert_computation_task_out_obj(
        client,
        task_out,
        project=sleepers_project,
        exp_task_state=RunningState.PUBLISHED,
        exp_pipeline_details=expected_pipeline_details_forced,
    )

    # now wait for the computation to finish
    task_out = await assert_pipeline_status(
        client, task_out.url, user_id, sleepers_project.uuid
    )


async def test_run_computation(
    minimal_configuration: None,
    client: TestClient,
    user_id: PositiveInt,
    project: Callable,
    fake_workbench_without_outputs: Dict[str, Any],
    update_project_workbench_with_comp_tasks: Callable,
    fake_workbench_computational_pipeline_details: PipelineDetails,
    fake_workbench_computational_pipeline_details_completed: PipelineDetails,
):
    sleepers_project = project(workbench=fake_workbench_without_outputs)
    # send a valid project with sleepers
    response = create_pipeline(
        client,
        project=sleepers_project,
        user_id=user_id,
        start_pipeline=True,
        expected_response_status_code=status.HTTP_201_CREATED,
    )
    task_out = ComputationTaskOut.parse_obj(response.json())

    # check the contents is correct: a pipeline that just started gets PUBLISHED
    assert_computation_task_out_obj(
        client,
        task_out,
        project=sleepers_project,
        exp_task_state=RunningState.PUBLISHED,
        exp_pipeline_details=fake_workbench_computational_pipeline_details,
    )

    # wait for the computation to start
    await assert_pipeline_status(
        client,
        task_out.url,
        user_id,
        sleepers_project.uuid,
        wait_for_states=[RunningState.STARTED],
    )

    # wait for the computation to finish (either by failing, success or abort)
    task_out = await assert_pipeline_status(
        client, task_out.url, user_id, sleepers_project.uuid
    )

    assert_computation_task_out_obj(
        client,
        task_out,
        project=sleepers_project,
        exp_task_state=RunningState.SUCCESS,
        exp_pipeline_details=fake_workbench_computational_pipeline_details_completed,
    )

    # FIXME: currently the webserver is the one updating the projects table so we need to fake this by copying the run_hash
    update_project_workbench_with_comp_tasks(str(sleepers_project.uuid))
    # run again should return a 422 cause everything is uptodate
    response = create_pipeline(
        client,
        project=sleepers_project,
        user_id=user_id,
        start_pipeline=True,
        expected_response_status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
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
    response = create_pipeline(
        client,
        project=sleepers_project,
        user_id=user_id,
        start_pipeline=True,
        expected_response_status_code=status.HTTP_201_CREATED,
        force_restart=True,
    )
    task_out = ComputationTaskOut.parse_obj(response.json())
    # check the contents is correct
    assert_computation_task_out_obj(
        client,
        task_out,
        project=sleepers_project,
        exp_task_state=RunningState.PUBLISHED,
        exp_pipeline_details=expected_pipeline_details_forced,  # NOTE: here the pipeline already ran so its states are different
    )

    # wait for the computation to finish
    task_out = await assert_pipeline_status(
        client, task_out.url, user_id, sleepers_project.uuid
    )
    assert_computation_task_out_obj(
        client,
        task_out,
        project=sleepers_project,
        exp_task_state=RunningState.SUCCESS,
        exp_pipeline_details=fake_workbench_computational_pipeline_details_completed,
    )


async def test_abort_computation(
    minimal_configuration: None,
    client: TestClient,
    user_id: PositiveInt,
    project: Callable,
    fake_workbench_without_outputs: Dict[str, Any],
    fake_workbench_computational_pipeline_details: PipelineDetails,
):
    sleepers_project = project(workbench=fake_workbench_without_outputs)
    # send a valid project with sleepers
    response = create_pipeline(
        client,
        project=sleepers_project,
        user_id=user_id,
        start_pipeline=True,
        expected_response_status_code=status.HTTP_201_CREATED,
    )
    task_out = ComputationTaskOut.parse_obj(response.json())

    # check the contents is correctb
    assert_computation_task_out_obj(
        client,
        task_out,
        project=sleepers_project,
        exp_task_state=RunningState.PUBLISHED,
        exp_pipeline_details=fake_workbench_computational_pipeline_details,
    )

    # wait until the pipeline is started
    task_out = await assert_pipeline_status(
        client,
        task_out.url,
        user_id,
        sleepers_project.uuid,
        wait_for_states=[RunningState.STARTED],
    )
    assert (
        task_out.state == RunningState.STARTED
    ), f"pipeline is not in the expected starting state but in {task_out.state}"
    assert task_out.url == f"{client.base_url}/v2/computations/{sleepers_project.uuid}"
    assert (
        task_out.stop_url
        == f"{client.base_url}/v2/computations/{sleepers_project.uuid}:stop"
    )

    # now abort the pipeline
    response = client.post(f"{task_out.stop_url}", json={"user_id": user_id})
    assert (
        response.status_code == status.HTTP_202_ACCEPTED
    ), f"response code is {response.status_code}, error: {response.text}"
    task_out = ComputationTaskOut.parse_obj(response.json())
    assert (
        str(task_out.url)
        == f"{client.base_url}/v2/computations/{sleepers_project.uuid}"
    )
    assert task_out.stop_url == None

    # check that the pipeline is aborted/stopped
    task_out = await assert_pipeline_status(
        client,
        task_out.url,
        user_id,
        sleepers_project.uuid,
        wait_for_states=[RunningState.ABORTED],
    )
    assert task_out.state == RunningState.ABORTED


async def test_update_and_delete_computation(
    minimal_configuration: None,
    client: TestClient,
    user_id: PositiveInt,
    project: Callable,
    fake_workbench_without_outputs: Dict[str, Any],
    fake_workbench_computational_pipeline_details_not_started: PipelineDetails,
    fake_workbench_computational_pipeline_details: PipelineDetails,
):
    sleepers_project = project(workbench=fake_workbench_without_outputs)
    # send a valid project with sleepers
    response = create_pipeline(
        client,
        project=sleepers_project,
        user_id=user_id,
        start_pipeline=False,
        expected_response_status_code=status.HTTP_201_CREATED,
    )
    task_out = ComputationTaskOut.parse_obj(response.json())

    # check the contents is correctb
    assert_computation_task_out_obj(
        client,
        task_out,
        project=sleepers_project,
        exp_task_state=RunningState.NOT_STARTED,
        exp_pipeline_details=fake_workbench_computational_pipeline_details_not_started,
    )

    # update the pipeline
    response = create_pipeline(
        client,
        project=sleepers_project,
        user_id=user_id,
        start_pipeline=False,
        expected_response_status_code=status.HTTP_201_CREATED,
    )
    task_out = ComputationTaskOut.parse_obj(response.json())

    # check the contents is correctb
    assert_computation_task_out_obj(
        client,
        task_out,
        project=sleepers_project,
        exp_task_state=RunningState.NOT_STARTED,
        exp_pipeline_details=fake_workbench_computational_pipeline_details_not_started,
    )

    # update the pipeline
    response = create_pipeline(
        client,
        project=sleepers_project,
        user_id=user_id,
        start_pipeline=False,
        expected_response_status_code=status.HTTP_201_CREATED,
    )
    task_out = ComputationTaskOut.parse_obj(response.json())

    # check the contents is correctb
    assert_computation_task_out_obj(
        client,
        task_out,
        project=sleepers_project,
        exp_task_state=RunningState.NOT_STARTED,
        exp_pipeline_details=fake_workbench_computational_pipeline_details_not_started,
    )

    # start it now
    response = create_pipeline(
        client,
        project=sleepers_project,
        user_id=user_id,
        start_pipeline=True,
        expected_response_status_code=status.HTTP_201_CREATED,
    )
    task_out = ComputationTaskOut.parse_obj(response.json())
    # check the contents is correctb
    assert_computation_task_out_obj(
        client,
        task_out,
        project=sleepers_project,
        exp_task_state=RunningState.PUBLISHED,
        exp_pipeline_details=fake_workbench_computational_pipeline_details,
    )

    # wait until the pipeline is started
    task_out = await assert_pipeline_status(
        client,
        task_out.url,
        user_id,
        sleepers_project.uuid,
        wait_for_states=[RunningState.STARTED],
    )
    assert (
        task_out.state == RunningState.STARTED
    ), f"pipeline is not in the expected starting state but in {task_out.state}"

    # now try to update the pipeline, is expected to be forbidden
    response = create_pipeline(
        client,
        project=sleepers_project,
        user_id=user_id,
        start_pipeline=False,
        expected_response_status_code=status.HTTP_403_FORBIDDEN,
    )

    # try to delete the pipeline, is expected to be forbidden if force parameter is false (default)
    response = client.delete(task_out.url, json={"user_id": user_id})
    assert (
        response.status_code == status.HTTP_403_FORBIDDEN
    ), f"response code is {response.status_code}, error: {response.text}"

    # try again with force=True this should abort and delete the pipeline
    response = client.delete(task_out.url, json={"user_id": user_id, "force": True})
    assert (
        response.status_code == status.HTTP_204_NO_CONTENT
    ), f"response code is {response.status_code}, error: {response.text}"


def test_pipeline_with_no_comp_services_still_create_correct_comp_tasks(
    minimal_configuration: None,
    client: TestClient,
    user_id: PositiveInt,
    project: Callable,
    jupyter_service: Dict[str, Any],
):
    # create a workbench with just a dynamic service
    project_with_dynamic_node = project(
        workbench={
            "39e92f80-9286-5612-85d1-639fa47ec57d": {
                "key": jupyter_service["image"]["name"],
                "version": jupyter_service["image"]["tag"],
                "label": "my sole dynamic service",
            }
        }
    )

    # this pipeline is not runnable as there are no computational services
    response = create_pipeline(
        client,
        project=project_with_dynamic_node,
        user_id=user_id,
        start_pipeline=True,
        expected_response_status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
    )

    # still this pipeline shall be createable if we do not want to start it
    response = create_pipeline(
        client,
        project=project_with_dynamic_node,
        user_id=user_id,
        start_pipeline=False,
        expected_response_status_code=status.HTTP_201_CREATED,
    )
    assert (
        response.status_code == status.HTTP_201_CREATED
    ), f"response code is {response.status_code}, error: {response.text}"


def test_pipeline_with_control_pipeline_made_of_dynamic_services_are_allowed(
    minimal_configuration: None,
    client: TestClient,
    user_id: PositiveInt,
    project: Callable,
    jupyter_service: Dict[str, Any],
):
    # create a workbench with just 2 dynamic service in a cycle
    project_with_dynamic_node = project(
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
        }
    )

    # this pipeline is not runnable as there are no computational services
    response = client.post(
        COMPUTATION_URL,
        json={
            "user_id": user_id,
            "project_id": str(project_with_dynamic_node.uuid),
            "start_pipeline": True,
        },
    )
    assert (
        response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    ), f"response code is {response.status_code}, error: {response.text}"

    # still this pipeline shall be createable if we do not want to start it
    response = client.post(
        COMPUTATION_URL,
        json={
            "user_id": user_id,
            "project_id": str(project_with_dynamic_node.uuid),
            "start_pipeline": False,
        },
    )
    assert (
        response.status_code == status.HTTP_201_CREATED
    ), f"response code is {response.status_code}, error: {response.text}"


def test_pipeline_with_cycle_containing_a_computational_service_is_forbidden(
    minimal_configuration: None,
    client: TestClient,
    user_id: PositiveInt,
    project: Callable,
    sleeper_service: Dict[str, Any],
    jupyter_service: Dict[str, Any],
):
    # create a workbench with just 2 dynamic service in a cycle
    project_with_cycly_and_comp_service = project(
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
        }
    )

    # this pipeline is not runnable as there are no computational services and it contains a cycle
    response = client.post(
        COMPUTATION_URL,
        json={
            "user_id": user_id,
            "project_id": str(project_with_cycly_and_comp_service.uuid),
            "start_pipeline": True,
        },
    )
    assert (
        response.status_code == status.HTTP_403_FORBIDDEN
    ), f"response code is {response.status_code}, error: {response.text}"

    # still this pipeline shall be createable if we do not want to start it
    response = client.post(
        COMPUTATION_URL,
        json={
            "user_id": user_id,
            "project_id": str(project_with_cycly_and_comp_service.uuid),
            "start_pipeline": False,
        },
    )
    assert (
        response.status_code == status.HTTP_201_CREATED
    ), f"response code is {response.status_code}, error: {response.text}"


async def test_burst_create_computations(
    minimal_configuration: None,
    async_client: AsyncClient,
    user_id: PositiveInt,
    project: Callable,
    fake_workbench_without_outputs: Dict[str, Any],
    update_project_workbench_with_comp_tasks: Callable,
    fake_workbench_computational_pipeline_details: PipelineDetails,
    fake_workbench_computational_pipeline_details_completed: PipelineDetails,
):
    sleepers_project = project(workbench=fake_workbench_without_outputs)
    sleepers_project2 = project(workbench=fake_workbench_without_outputs)

    async def create_pipeline(project: ProjectAtDB, start_pipeline: bool):
        return await async_client.post(
            COMPUTATION_URL,
            json={
                "user_id": user_id,
                "project_id": str(project.uuid),
                "start_pipeline": start_pipeline,
            },
            timeout=60,
        )

    NUMBER_OF_CALLS = 4

    # creating 4 pipelines without starting should return 4 times 201
    # the second pipeline should also return a 201
    responses = await asyncio.gather(
        *(
            [
                create_pipeline(sleepers_project, start_pipeline=False)
                for _ in range(NUMBER_OF_CALLS)
            ]
            + [create_pipeline(sleepers_project2, start_pipeline=False)]
        )
    )
    received_status_codes = [r.status_code for r in responses]
    assert status.HTTP_201_CREATED in received_status_codes
    assert received_status_codes.count(status.HTTP_201_CREATED) == NUMBER_OF_CALLS + 1

    # starting 4 pipelines should return 1 time 201 and 3 times 403
    # the second pipeline should return a 201
    responses = await asyncio.gather(
        *(
            [
                create_pipeline(sleepers_project, start_pipeline=True)
                for _ in range(NUMBER_OF_CALLS)
            ]
            + [create_pipeline(sleepers_project2, start_pipeline=False)]
        )
    )
    received_status_codes = [r.status_code for r in responses]
    assert received_status_codes.count(status.HTTP_201_CREATED) == 2
    assert received_status_codes.count(status.HTTP_403_FORBIDDEN) == (
        NUMBER_OF_CALLS - 1
    )
