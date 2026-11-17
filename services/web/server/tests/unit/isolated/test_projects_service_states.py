import json
import warnings
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest
from models_library.api_schemas_directorv2.comp_runs import ComputationRunStateRpcGet
from models_library.groups import GroupID
from models_library.projects_nodes import NodeShareState, NodeShareStatus, NodeState
from models_library.projects_nodes_io import NodeID
from models_library.projects_pipeline import ComputationTask, PipelineDetails
from models_library.projects_state import ProjectShareState, ProjectStatus, RunningState
from models_library.users import UserID
from pytest_mock import MockerFixture
from simcore_service_webserver.projects import _projects_service
from simcore_service_webserver.projects.models import ProjectDict


@pytest.mark.parametrize(
    "latest_states,expected_state",
    [
        ([], RunningState.NOT_STARTED),
        (None, RunningState.UNKNOWN),
    ],
)
async def test_add_projects_states_distinguishes_no_run_from_retrieval_failure(
    mocker: MockerFixture,
    latest_states: list[ComputationRunStateRpcGet] | None,
    expected_state: RunningState,
):
    project = {"uuid": f"{uuid4()}"}
    project_share_state = ProjectShareState(
        current_user_groupids=[],
        locked=False,
        status=ProjectStatus.CLOSED,
    )
    mocker.patch.object(
        _projects_service,
        "_list_pipelines_latest_states_or_none",
        AsyncMock(return_value=latest_states),
    )
    mocker.patch.object(
        _projects_service,
        "_get_project_share_state",
        AsyncMock(return_value=project_share_state),
    )

    projects = await _projects_service.add_projects_states_for_user(
        app=Mock(),
        projects=[project],
        user_id=UserID(1),
    )

    assert projects[0]["state"]["state"]["value"] == expected_state


@pytest.mark.parametrize(
    "node_in_computation,expected_current_status",
    [
        (True, RunningState.PUBLISHED),
        (False, RunningState.STARTED),
    ],
)
async def test_add_project_states_for_user_produces_json_native_node_states(
    mocker: MockerFixture,
    node_in_computation: bool,
    expected_current_status: RunningState,
):
    node_id: NodeID = uuid4()
    dependency_id: NodeID = uuid4()
    project: ProjectDict = {
        "uuid": f"{uuid4()}",
        "workbench": {
            f"{node_id}": {
                "key": "simcore/services/comp/itis/sleeper",
                "version": "2.1.7",
                "label": "sleeper",
                "state": {
                    "modified": True,
                    "dependencies": [f"{dependency_id}"],
                    "currentStatus": RunningState.SUCCESS.value,
                },
            }
        },
    }

    node_states: dict[NodeID, NodeState] = (
        {
            node_id: NodeState(
                modified=False,
                dependencies={dependency_id},
                current_status=RunningState.PUBLISHED,
                progress=0.4,
            )
        }
        if node_in_computation
        else {}
    )
    computation_task = ComputationTask(
        id=uuid4(),
        state=RunningState.PUBLISHED,
        result=None,
        iteration=1,
        started=None,
        stopped=None,
        submitted=None,
        pipeline_details=PipelineDetails(adjacency_list={}, progress=0.4, node_states=node_states),
    )

    mocker.patch.object(
        _projects_service,
        "_get_project_share_state",
        AsyncMock(
            return_value=ProjectShareState(
                current_user_groupids=[],
                locked=False,
                status=ProjectStatus.CLOSED,
            )
        ),
    )
    mocker.patch.object(
        _projects_service,
        "_get_node_share_state",
        AsyncMock(
            return_value=NodeShareState(
                locked=True,
                current_user_groupids=[GroupID(42)],
                status=NodeShareStatus.OPENED,
            )
        ),
    )
    mocker.patch.object(
        _projects_service.director_v2_service,
        "get_computation_task",
        AsyncMock(return_value=computation_task),
    )
    mocker.patch.object(
        _projects_service.users_service,
        "get_user_primary_group_id",
        AsyncMock(return_value=GroupID(42)),
    )

    with warnings.catch_warnings(record=True) as captured_warnings:
        warnings.simplefilter("always")
        updated_project = await _projects_service.add_project_states_for_user(
            app=Mock(),
            user_id=UserID(1),
            project=project,
        )

    serializer_warnings = [w for w in captured_warnings if "Pydantic serializer" in str(w.message)]
    assert not serializer_warnings, f"{[str(w.message) for w in serializer_warnings]=}"

    node_state = updated_project["workbench"][f"{node_id}"]["state"]
    # must be storable/serializable as part of the project document
    assert json.loads(json.dumps(updated_project))

    assert node_state["currentStatus"] == expected_current_status.value
    assert node_state["lock_state"] == {
        "locked": True,
        "current_user_groupids": [42],
        "status": NodeShareStatus.OPENED.value,
    }
    # the dependency stored in the workbench is preserved in both cases
    assert node_state["dependencies"] == [f"{dependency_id}"]
    if node_in_computation:
        assert node_state["progress"] == 0.4
        assert updated_project["workbench"][f"{node_id}"]["progress"] == 40
    else:
        assert "progress" not in node_state
