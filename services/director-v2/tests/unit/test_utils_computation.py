# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=protected-access

from pathlib import Path

import faker
import pytest
from models_library.projects_state import RunningState
from simcore_service_director_v2.models.comp_tasks import CompTaskAtDB
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
    return CompTaskAtDB.model_validate_json(fake_task_file.read_text())


# NOTE: these parametrizations are made to mimic something like a sleepers project
@pytest.mark.parametrize(
    "task_states, exp_pipeline_state",
    [
        pytest.param(
            [
                (RunningState.UNKNOWN),
                (RunningState.UNKNOWN),
                (RunningState.UNKNOWN),
                (RunningState.UNKNOWN),
                (RunningState.UNKNOWN),
            ],
            RunningState.UNKNOWN,
            id="initial task states unknown = unknown state",
        ),
        pytest.param(
            [
                (RunningState.NOT_STARTED),
                (RunningState.NOT_STARTED),
                (RunningState.NOT_STARTED),
                (RunningState.NOT_STARTED),
                (RunningState.NOT_STARTED),
            ],
            RunningState.NOT_STARTED,
            id="not_started tasks = not_started pipeline",
        ),
        pytest.param(
            [
                (RunningState.PUBLISHED),
                (RunningState.PUBLISHED),
                (RunningState.NOT_STARTED),
                (RunningState.NOT_STARTED),
                (RunningState.NOT_STARTED),
            ],
            RunningState.PUBLISHED,
            id="not_started tasks transitioning to published = not_started pipeline",
        ),
        pytest.param(
            [
                (RunningState.PUBLISHED),
                (RunningState.PUBLISHED),
                (RunningState.PUBLISHED),
                (RunningState.PUBLISHED),
                (RunningState.PUBLISHED),
            ],
            RunningState.PUBLISHED,
            id="published tasks  = published pipeline",
        ),
        pytest.param(
            [
                (RunningState.PENDING),
                (RunningState.PUBLISHED),
                (RunningState.PUBLISHED),
                (RunningState.PUBLISHED),
                (RunningState.PUBLISHED),
            ],
            RunningState.PENDING,
            id="published transitioning to pending tasks = pending",
        ),
        pytest.param(
            [
                (RunningState.STARTED),
                (RunningState.PUBLISHED),
                (RunningState.PUBLISHED),
                (RunningState.PUBLISHED),
                (RunningState.PUBLISHED),
            ],
            RunningState.STARTED,
            id="1 task started = started pipeline",
        ),
        pytest.param(
            [
                (RunningState.SUCCESS),
                (RunningState.PUBLISHED),
                (RunningState.PUBLISHED),
                (RunningState.PUBLISHED),
                (RunningState.PUBLISHED),
            ],
            RunningState.STARTED,
            id="1 task completed = started pipeline",
        ),
        pytest.param(
            [
                (RunningState.SUCCESS),
                (RunningState.PENDING),
                (RunningState.PENDING),
                (RunningState.PUBLISHED),
                (RunningState.PUBLISHED),
            ],
            RunningState.STARTED,
            id="1 task completed, other pending = started pipeline",
        ),
        pytest.param(
            [
                (RunningState.SUCCESS),
                (RunningState.SUCCESS),
                (RunningState.PENDING),
                (RunningState.PENDING),
                (RunningState.PUBLISHED),
            ],
            RunningState.STARTED,
            id="2 tasks completed, continuing = started pipeline",
        ),
        pytest.param(
            [
                (RunningState.SUCCESS),
                (RunningState.SUCCESS),
                (RunningState.SUCCESS),
                (RunningState.SUCCESS),
                (RunningState.PUBLISHED),
            ],
            RunningState.STARTED,
            id="4 tasks completed, continuing = started pipeline",
        ),
        pytest.param(
            [
                (RunningState.SUCCESS),
                (RunningState.SUCCESS),
                (RunningState.SUCCESS),
                (RunningState.SUCCESS),
                (RunningState.PENDING),
            ],
            RunningState.STARTED,
            id="4 tasks completed, 1 pending = started pipeline",
        ),
        pytest.param(
            [
                (RunningState.SUCCESS),
                (RunningState.SUCCESS),
                (RunningState.SUCCESS),
                (RunningState.SUCCESS),
                (RunningState.SUCCESS),
            ],
            RunningState.SUCCESS,
            id="5 tasks completed  = completed pipeline",
        ),
        pytest.param(
            [
                (RunningState.SUCCESS),
                (RunningState.FAILED),
                (RunningState.SUCCESS),
                (RunningState.STARTED),
                (RunningState.PUBLISHED),
            ],
            RunningState.STARTED,
            id="2 tasks completed, 1 task failed, 1 started, 1 published  = started pipeline",
        ),
        pytest.param(
            [
                (RunningState.SUCCESS),
                (RunningState.FAILED),
                (RunningState.ABORTED),
                (RunningState.STARTED),
            ],
            RunningState.STARTED,
            id="if any task in published, started, pending  = started pipeline",
        ),
        pytest.param(
            [
                (RunningState.SUCCESS),
                (RunningState.FAILED),
                (RunningState.ABORTED),
                (RunningState.PUBLISHED),
            ],
            RunningState.STARTED,
            id="if any task in published, started, pending  = started pipeline",
        ),
        pytest.param(
            [
                (RunningState.SUCCESS),
                (RunningState.FAILED),
                (RunningState.ABORTED),
                (RunningState.PENDING),
            ],
            RunningState.STARTED,
            id="if any task in published, started, pending  = started pipeline",
        ),
        pytest.param(
            [
                (RunningState.SUCCESS),
                (RunningState.FAILED),
                (RunningState.ABORTED),
            ],
            RunningState.FAILED,
            id="any number of success",
        ),
        pytest.param(
            [
                (RunningState.SUCCESS),
                (RunningState.SUCCESS),
                (RunningState.FAILED),
            ],
            RunningState.FAILED,
            id="any number of success and 1 failed = failed",
        ),
        pytest.param(
            [
                (RunningState.SUCCESS),
                (RunningState.SUCCESS),
                (RunningState.ABORTED),
            ],
            RunningState.ABORTED,
            id="any number of success and 1 aborted = aborted",
        ),
        pytest.param(
            [
                (RunningState.SUCCESS),
                (RunningState.PENDING),
                (RunningState.NOT_STARTED),
            ],
            RunningState.STARTED,
            id="any number of success and 1 aborted = aborted",
        ),
        pytest.param(
            [],
            RunningState.UNKNOWN,
            id="empty tasks (empty project or full of dynamic services) = unknown",
        ),
        pytest.param(
            [
                (RunningState.WAITING_FOR_CLUSTER),
                (RunningState.PUBLISHED),
                (RunningState.PUBLISHED),
            ],
            RunningState.WAITING_FOR_CLUSTER,
            id="published and waiting for cluster = waiting for cluster",
        ),
    ],
)
def test_get_pipeline_state_from_task_states(
    task_states: list[RunningState],
    exp_pipeline_state: RunningState,
    fake_task: CompTaskAtDB,
):
    tasks: list[CompTaskAtDB] = [
        fake_task.model_copy(deep=True, update={"state": s}) for s in task_states
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
