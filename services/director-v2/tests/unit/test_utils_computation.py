# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=protected-access

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


@pytest.mark.parametrize(
    "task_states, exp_pipeline_state",
    [
        pytest.param(
            [
                (RunningState.PUBLISHED),
                (RunningState.PENDING),
                (RunningState.PUBLISHED),
            ],
            RunningState.PENDING,
            id="unconnected published/pending tasks = pending",
        ),
        pytest.param(
            [
                (RunningState.PUBLISHED),
                (RunningState.PUBLISHED),
                (RunningState.PUBLISHED),
            ],
            RunningState.PUBLISHED,
            id="unconnected published tasks = published",
        ),
        pytest.param(
            [
                (RunningState.NOT_STARTED),
                (RunningState.NOT_STARTED),
            ],
            RunningState.NOT_STARTED,
            id="unconnected not_started tasks = not_started",
        ),
        pytest.param(
            [
                (RunningState.SUCCESS),
                (RunningState.SUCCESS),
            ],
            RunningState.SUCCESS,
            id="unconnected successfull tasks = success",
        ),
        pytest.param(
            [
                (RunningState.PENDING),
                (RunningState.PENDING),
            ],
            RunningState.PENDING,
            id="unconnected pending tasks = pending",
        ),
        pytest.param(
            [
                (RunningState.SUCCESS),
                (RunningState.SUCCESS),
                (RunningState.FAILED),
                (RunningState.ABORTED),
            ],
            RunningState.FAILED,
            id="any number of success and 1 failed = failed",
        ),
        pytest.param(
            [
                (RunningState.SUCCESS),
                (RunningState.SUCCESS),
                (RunningState.PENDING),
                (RunningState.FAILED),
                (RunningState.FAILED),
                (RunningState.PENDING),
                (RunningState.PUBLISHED),
                (RunningState.ABORTED),
            ],
            RunningState.STARTED,
            id="any number of unconnected success and failed failed with pending/published = started",
        ),
        pytest.param(
            [
                (RunningState.STARTED),
                (RunningState.FAILED),
            ],
            RunningState.STARTED,
            id="any number of unconnected success and failed failed with pending/published = started",
        ),
        pytest.param(
            [
                (RunningState.SUCCESS),
                (RunningState.PENDING),
                (RunningState.PENDING),
            ],
            RunningState.STARTED,
            id="any number of unconnected success and failed failed with pending/published = started",
        ),
        pytest.param(
            [
                (RunningState.SUCCESS),
                (RunningState.PENDING),
                (RunningState.PUBLISHED),
            ],
            RunningState.STARTED,
            id="any number of unconnected success and failed failed with pending/published = started",
        ),
        pytest.param(
            [
                (RunningState.SUCCESS),
                (RunningState.ABORTED),
                (RunningState.FAILED),
                (RunningState.PENDING),
            ],
            RunningState.STARTED,
            id="any number of unconnected success and failed failed with pending/published = started",
        ),
        pytest.param(
            [
                (RunningState.SUCCESS),
                (RunningState.ABORTED),
                (RunningState.ABORTED),
            ],
            RunningState.ABORTED,
            id="any number of unconnected success and aborted without pending/published = aborted",
        ),
        pytest.param(
            [],
            RunningState.NOT_STARTED,
            id="empty tasks (empty project or full of dynamic services) = not_started",
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
