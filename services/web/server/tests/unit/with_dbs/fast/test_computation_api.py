# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name


import faker
import pytest

from models_library.projects import RunningState
from simcore_postgres_database.models.comp_pipeline import StateType
from simcore_service_webserver.computation_api import (
    convert_state_from_db,
)

fake = faker.Faker()

NodeID = str


@pytest.mark.parametrize(
    "db_state, expected_state",
    [
        (StateType.FAILED, RunningState.FAILED),
        (StateType.PENDING, RunningState.PENDING),
        (StateType.RUNNING, RunningState.STARTED),
        (StateType.SUCCESS, RunningState.SUCCESS),
        (StateType.NOT_STARTED, RunningState.NOT_STARTED),
    ],
)
def test_convert_state_from_db(db_state: int, expected_state: RunningState):
    assert convert_state_from_db(db_state) == expected_state
