from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest
from models_library.api_schemas_directorv2.comp_runs import ComputationRunStateRpcGet
from models_library.projects_state import ProjectShareState, ProjectStatus, RunningState
from models_library.users import UserID
from pytest_mock import MockerFixture
from simcore_service_webserver.projects import _projects_service


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
