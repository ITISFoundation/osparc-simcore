# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name


import pytest
from models_library.projects_state import RunningState
from simcore_postgres_database.models.comp_pipeline import StateType
from simcore_service_webserver.db_listener._utils import convert_state_from_db


@pytest.mark.parametrize(
    "db_state, expected_state",
    [
        (StateType.FAILED, RunningState.FAILED),
        (StateType.PENDING, RunningState.PENDING),
        (StateType.RUNNING, RunningState.STARTED),
        (StateType.SUCCESS, RunningState.SUCCESS),
        (StateType.NOT_STARTED, RunningState.NOT_STARTED),
        (StateType.WAITING_FOR_RESOURCES, RunningState.WAITING_FOR_RESOURCES),
        (StateType.WAITING_FOR_CLUSTER, RunningState.WAITING_FOR_CLUSTER),
    ],
)
def test_convert_state_from_db(db_state: StateType, expected_state: RunningState):
    assert convert_state_from_db(db_state) == expected_state
