# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=protected-access


from datetime import datetime
from pathlib import Path
from typing import List

import faker
import pytest
from models_library.projects_state import RunningState
from simcore_service_director_v2.models.domains.comp_tasks import CompTaskAtDB
from simcore_service_director_v2.utils.computations import (
    get_pipeline_state_from_task_states,
    is_pipeline_running,
    is_pipeline_stopped,
)

fake = faker.Faker()


@pytest.fixture(scope="session")
def fake_task_file(mocks_dir: Path):
    task_file = mocks_dir / "fake_task.json"
    assert task_file.exists()
    return task_file


@pytest.fixture(scope="session")
def fake_task(fake_task_file: Path) -> CompTaskAtDB:
    return CompTaskAtDB.parse_file(fake_task_file)


CELERY_PUBLICATION_TIMEOUT = 120


def _lazy_evaluate_time(time_fct: str) -> datetime:
    # pylint: disable=eval-used
    # pylint: disable=unused-import
    from datetime import timedelta

    return eval(time_fct)


@pytest.mark.parametrize(
    "task_states, exp_pipeline_state",
    [
        (
            # pipeline is published if all the nodes are published AND time is within publication timeout
            [
                (RunningState.PUBLISHED),
                (RunningState.PENDING),
                (RunningState.PUBLISHED),
            ],
            RunningState.PENDING,
        ),
        (
            # pipeline is published if all the nodes are published AND time is within publication timeout
            [
                (RunningState.PUBLISHED),
                (RunningState.PUBLISHED),
                (RunningState.PUBLISHED),
            ],
            RunningState.PUBLISHED,
        ),
        (
            # not started pipeline (all nodes are in non started mode)
            [
                (RunningState.NOT_STARTED),
                (RunningState.NOT_STARTED),
            ],
            RunningState.NOT_STARTED,
        ),
        (
            # successful pipeline if ALL of the node are successful
            [
                (RunningState.SUCCESS),
                (RunningState.SUCCESS),
            ],
            RunningState.SUCCESS,
        ),
        (
            # pending pipeline if ALL of the node are pending
            [
                (RunningState.PENDING),
                (RunningState.PENDING),
            ],
            RunningState.PENDING,
        ),
        (
            # if one failed out of the other successfull ones then fails
            [
                (RunningState.SUCCESS),
                (RunningState.SUCCESS),
                (RunningState.FAILED),
            ],
            RunningState.FAILED,
        ),
        (
            # started pipeline even if one node failed
            [
                (RunningState.SUCCESS),
                (RunningState.PENDING),
                (RunningState.FAILED),
                (RunningState.PENDING),
            ],
            RunningState.STARTED,
        ),
        (
            # started pipeline if any of the node is started
            [
                (RunningState.STARTED),
                (RunningState.FAILED),
            ],
            RunningState.STARTED,
        ),
        (
            # started pipeline if any of the node is started
            [
                (RunningState.SUCCESS),
                (RunningState.PENDING),
                (RunningState.PENDING),
            ],
            RunningState.STARTED,
        ),
        (
            # started pipeline if any of the node is started
            [
                (RunningState.SUCCESS),
                (RunningState.PENDING),
                (RunningState.PUBLISHED),
            ],
            RunningState.STARTED,
        ),
        (
            # ABORTED pipeline if any of the node is aborted
            [
                (RunningState.SUCCESS),
                (RunningState.ABORTED),
                (RunningState.PENDING),
            ],
            RunningState.ABORTED,
        ),
        (
            # empty tasks (could be an empty project or filled with dynamic services)
            [],
            RunningState.NOT_STARTED,
        ),
    ],
)
def test_get_pipeline_state_from_task_states(
    task_states: List[RunningState],
    exp_pipeline_state: RunningState,
    fake_task: CompTaskAtDB,
):
    tasks: List[CompTaskAtDB] = [
        fake_task.copy(deep=True, update={"state": s}) for s in task_states
    ]

    pipeline_state: RunningState = get_pipeline_state_from_task_states(tasks)
    assert (
        pipeline_state == exp_pipeline_state
    ), f"task states are: {task_states}, got {pipeline_state} instead of {exp_pipeline_state}"


@pytest.mark.parametrize(
    "state,exp",
    [
        (RunningState.UNKNOWN, False),
        (RunningState.PUBLISHED, True),
        (RunningState.NOT_STARTED, False),
        (RunningState.PENDING, True),
        (RunningState.STARTED, True),
        (RunningState.RETRY, True),
        (RunningState.SUCCESS, False),
        (RunningState.FAILED, False),
        (RunningState.ABORTED, False),
    ],
)
def test_is_pipeline_running(state, exp: bool):
    assert (
        is_pipeline_running(state) is exp
    ), f"pipeline in {state}, i.e. running state should be {exp}"
    assert is_pipeline_stopped is not exp
