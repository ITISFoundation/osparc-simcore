# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name


from typing import Dict

import pytest
from models_library.projects import RunningState
from pytest_simcore.postgres_service import postgres_db
from simcore_postgres_database.models.comp_pipeline import (
    StateType
)
from simcore_service_webserver import computation_api
from simcore_service_webserver.computation_api import (
    convert_state_from_db,
    get_pipeline_state,
)


@pytest.mark.parametrize(
    "db_state, expected_state",
    [
        (StateType.FAILED, RunningState.failure),
        (StateType.PENDING, RunningState.pending),
        (StateType.RUNNING, RunningState.started),
        (StateType.SUCCESS, RunningState.success),
        (StateType.NOT_STARTED, RunningState.not_started),
    ],
)
def test_convert_state_from_db(db_state: int, expected_state: RunningState):
    assert convert_state_from_db(db_state) == expected_state


NodeID = str


@pytest.fixture
async def mock_get_task_states(
    loop, monkeypatch, task_states: Dict[NodeID, RunningState]
):
    async def return_node_to_state(*args, **kwargs):
        return task_states

    monkeypatch.setattr(computation_api, "get_task_states", return_node_to_state)


@pytest.mark.parametrize(
    "task_states, expected_pipeline_state",
    [
        (
            # not started pipeline (all nodes are in non started mode)
            {"task0": RunningState.not_started, "task1": RunningState.not_started},
            RunningState.not_started,
        ),
        (
            # successful pipeline if ALL of the node are successful
            {"task0": RunningState.success, "task1": RunningState.success},
            RunningState.success,
        ),
        (
            # pending pipeline if ALL of the node are pending
            {"task0": RunningState.pending, "task1": RunningState.pending},
            RunningState.pending,
        ),
        (
            # failed pipeline if any of the node is failed
            {"task0": RunningState.pending, "task1": RunningState.failure},
            RunningState.failure,
        ),
        (
            # started pipeline if any of the node is started
            {"task0": RunningState.started, "task1": RunningState.failure},
            RunningState.started,
        ),
        (
            # empty tasks (could be an empty project or filled with dynamic services)
            {},
            RunningState.not_started,
        ),
    ],
)
async def test_get_pipeline_state(
    mock_get_task_states, expected_pipeline_state: RunningState
):
    assert await get_pipeline_state({}, "fake_project") == expected_pipeline_state


@pytest.mark.parametrize(
    "undefined_task_states",
    [
        (
            # webserver crashed after setting tasks to pending
            {"task0": RunningState.pending, "task1": RunningState.pending},
        ),
    ],
)
async def test_recover_after_crash(undefined_task_states):

    pass
