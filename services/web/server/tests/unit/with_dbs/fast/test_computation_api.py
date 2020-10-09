# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name


from datetime import datetime, timedelta
from typing import Dict

import faker
import pytest

from models_library.projects import RunningState
from pytest_simcore.postgres_service import postgres_db
from simcore_postgres_database.models.comp_pipeline import StateType
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


@pytest.fixture
def mock_get_celery_publication_timeout(monkeypatch):
    def return_celery_publication_timeout(*args, **kwargs) -> int:
        return 120

    monkeypatch.setattr(
        computation_api,
        "get_celery_publication_timeout",
        return_celery_publication_timeout,
    )


fake = faker.Faker()


@pytest.mark.parametrize(
    "task_states, expected_pipeline_state",
    [
        (
            # not started pipeline (all nodes are in non started mode)
            {
                "task0": (RunningState.not_started, fake.date_time()),
                "task1": (RunningState.not_started, fake.date_time()),
            },
            RunningState.not_started,
        ),
        (
            # successful pipeline if ALL of the node are successful
            {
                "task0": (RunningState.success, fake.date_time()),
                "task1": (RunningState.success, fake.date_time()),
            },
            RunningState.success,
        ),
        (
            # pending pipeline if ALL of the node are pending
            {
                "task0": (RunningState.pending, fake.date_time()),
                "task1": (RunningState.pending, fake.date_time()),
            },
            RunningState.pending,
        ),
        (
            # failed pipeline if any of the node is failed
            {
                "task0": (RunningState.pending, fake.date_time()),
                "task1": (RunningState.failure, fake.date_time()),
            },
            RunningState.failure,
        ),
        (
            # started pipeline if any of the node is started
            {
                "task0": (RunningState.started, fake.date_time()),
                "task1": (RunningState.failure, fake.date_time()),
            },
            RunningState.started,
        ),
        (
            # pipeline is published if any of the node is published AND time is within publication timeout
            {
                "task0": (RunningState.published, datetime.utcnow()),
                "task1": (
                    RunningState.pending,
                    datetime.utcnow() - timedelta(seconds=75),
                ),
                "task2": (
                    RunningState.started,
                    datetime.utcnow() - timedelta(seconds=155),
                ),
            },
            RunningState.published,
        ),
        (
            # pipeline is published if any of the node is published AND time is within publication timeout
            {
                "task0": (
                    RunningState.published,
                    datetime.utcnow() - timedelta(seconds=175),
                ),
                "task1": (
                    RunningState.pending,
                    datetime.utcnow() - timedelta(seconds=145),
                ),
                "task2": (
                    RunningState.started,
                    datetime.utcnow() - timedelta(seconds=1555),
                ),
            },
            RunningState.not_started,
        ),
        (
            # empty tasks (could be an empty project or filled with dynamic services)
            {},
            RunningState.not_started,
        ),
    ],
)
async def test_get_pipeline_state(
    mock_get_task_states,
    mock_get_celery_publication_timeout,
    expected_pipeline_state: RunningState,
):
    pipeline_state = await get_pipeline_state({}, "fake_project")
    assert pipeline_state == expected_pipeline_state
