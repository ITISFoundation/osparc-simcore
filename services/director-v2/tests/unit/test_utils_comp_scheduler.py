# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name


import pytest
from models_library.projects_state import RunningState
from simcore_service_director_v2.utils.comp_scheduler import (
    COMPLETED_STATES,
    SCHEDULED_STATES,
)


@pytest.mark.parametrize(
    "state",
    [
        RunningState.PUBLISHED,
        RunningState.PENDING,
        RunningState.STARTED,
        RunningState.RETRY,
    ],
)
def test_scheduler_takes_care_of_runs_with_state(state: RunningState):
    assert state in SCHEDULED_STATES


@pytest.mark.parametrize(
    "state",
    [
        RunningState.SUCCESS,
        RunningState.ABORTED,
        RunningState.FAILED,
    ],
)
def test_scheduler_knows_these_are_completed_states(state: RunningState):
    assert state in COMPLETED_STATES


def test_scheduler_knows_all_the_states():
    assert COMPLETED_STATES.union(SCHEDULED_STATES).union(
        {RunningState.NOT_STARTED, RunningState.UNKNOWN}
    ) == set(RunningState)
