# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name


from datetime import datetime, timedelta
from typing import Dict

import faker
import pytest

from models_library.projects import RunningState
from simcore_postgres_database.models.comp_pipeline import StateType
from simcore_service_webserver import computation_api
from simcore_service_webserver.computation_api import (
    convert_state_from_db,
    get_pipeline_state,
)

fake = faker.Faker()

NodeID = str


@pytest.mark.parametrize(
    "db_state, expected_state",
    [
        (StateType.FAILED, RunningState.FAILURE),
        (StateType.PENDING, RunningState.PENDING),
        (StateType.RUNNING, RunningState.STARTED),
        (StateType.SUCCESS, RunningState.SUCCESS),
        (StateType.NOT_STARTED, RunningState.NOT_STARTED),
    ],
)
def test_convert_state_from_db(db_state: int, expected_state: RunningState):
    assert convert_state_from_db(db_state) == expected_state


@pytest.fixture
async def mock_get_task_states(
    loop, monkeypatch, task_states: Dict[NodeID, RunningState]
):
    async def return_node_to_state(*args, **kwargs):
        return task_states

    monkeypatch.setattr(computation_api, "get_task_states", return_node_to_state)


CELERY_PUBLICATION_TIMEOUT = 120


@pytest.fixture
def mock_get_celery_publication_timeout(monkeypatch):
    def return_celery_publication_timeout(*args, **kwargs) -> int:
        return CELERY_PUBLICATION_TIMEOUT

    monkeypatch.setattr(
        computation_api,
        "get_celery_publication_timeout",
        return_celery_publication_timeout,
    )


@pytest.mark.parametrize(
    "task_states, expected_pipeline_state",
    [
        (
            # pipeline is published if any of the node is published AND time is within publication timeout
            {
                "task0": (
                    RunningState.PUBLISHED,
                    datetime.utcnow(),
                ),
                "task1": (
                    RunningState.PENDING,
                    datetime.utcnow() - timedelta(seconds=75),
                ),
                "task2": (
                    RunningState.STARTED,
                    datetime.utcnow() - timedelta(seconds=155),
                ),
            },
            RunningState.PUBLISHED,
        ),
        (
            # pipeline is published if any of the node is published AND time is within publication timeout
            {
                "task0": (
                    RunningState.PUBLISHED,
                    datetime.utcnow() - timedelta(seconds=175),
                ),
                "task1": (
                    RunningState.PENDING,
                    datetime.utcnow() - timedelta(seconds=145),
                ),
                "task2": (
                    RunningState.STARTED,
                    datetime.utcnow() - timedelta(seconds=1555),
                ),
            },
            RunningState.NOT_STARTED,
        ),
        (
            # not started pipeline (all nodes are in non started mode)
            {
                "task0": (RunningState.NOT_STARTED, fake.date_time()),
                "task1": (RunningState.NOT_STARTED, fake.date_time()),
            },
            RunningState.NOT_STARTED,
        ),
        (
            # successful pipeline if ALL of the node are successful
            {
                "task0": (RunningState.SUCCESS, fake.date_time()),
                "task1": (RunningState.SUCCESS, fake.date_time()),
            },
            RunningState.SUCCESS,
        ),
        (
            # pending pipeline if ALL of the node are pending
            {
                "task0": (RunningState.PENDING, fake.date_time()),
                "task1": (RunningState.PENDING, fake.date_time()),
            },
            RunningState.PENDING,
        ),
        (
            # failed pipeline if any of the node is failed
            {
                "task0": (RunningState.PENDING, fake.date_time()),
                "task1": (RunningState.FAILURE, fake.date_time()),
            },
            RunningState.FAILURE,
        ),
        (
            # started pipeline if any of the node is started
            {
                "task0": (RunningState.STARTED, fake.date_time()),
                "task1": (RunningState.FAILURE, fake.date_time()),
            },
            RunningState.STARTED,
        ),
        (
            # empty tasks (could be an empty project or filled with dynamic services)
            {},
            RunningState.NOT_STARTED,
        ),
    ],
)
async def test_get_pipeline_state(
    mock_get_task_states,
    mock_get_celery_publication_timeout,
    expected_pipeline_state: RunningState,
):
    FAKE_APP = {}
    FAKE_PROJECT = "project_id"
    pipeline_state = await get_pipeline_state(FAKE_APP, FAKE_PROJECT)
    assert pipeline_state == expected_pipeline_state
