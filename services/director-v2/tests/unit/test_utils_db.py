import pytest
from models_library.projects_state import RunningState
from simcore_postgres_database.models.comp_pipeline import StateType
from simcore_service_director_v2.utils.db import (
    DB_TO_RUNNING_STATE,
    RUNNING_STATE_TO_DB,
)


@pytest.mark.parametrize("input_running_state", RunningState)
def test_running_state_to_db(input_running_state: RunningState):
    assert input_running_state in RUNNING_STATE_TO_DB


@pytest.mark.parametrize("input_state_type", StateType)
def test_db_to_running_state(input_state_type: StateType):
    assert input_state_type in DB_TO_RUNNING_STATE
