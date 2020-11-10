# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=protected-access


from datetime import datetime
from pathlib import Path
from typing import List

import faker
import pytest
from models_library.projects import RunningState
from simcore_service_director_v2.models.domains.comp_tasks import CompTaskAtDB
from simcore_service_director_v2.utils.computations import (
    get_pipeline_state_from_task_states,
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


@pytest.fixture(scope="session")
def publication_timeout() -> int:
    return 60


CELERY_PUBLICATION_TIMEOUT = 120


def _lazy_evaluate_time(time_fct: str) -> datetime:
    # pylint: disable=eval-used
    # pylint: disable=unused-import
    from datetime import timedelta

    return eval(time_fct)


@pytest.fixture
def configure_celery_timeout(monkeypatch):
    monkeypatch.setenv("CELERY_PUBLICATION_TIMEOUT", str(CELERY_PUBLICATION_TIMEOUT))


@pytest.mark.parametrize(
    "task_states, exp_pipeline_state",
    [
        (
            # pipeline is published if all the nodes are published AND time is within publication timeout
            [
                (RunningState.PUBLISHED, "datetime.utcnow()"),
                (RunningState.PENDING, "datetime.utcnow()-timedelta(seconds=75)"),
                (RunningState.PUBLISHED, "datetime.utcnow()-timedelta(seconds=155)"),
            ],
            RunningState.PENDING,
        ),
        (
            # pipeline is published if all the nodes are published AND time is within publication timeout
            [
                (RunningState.PUBLISHED, "datetime.utcnow()"),
                (RunningState.PUBLISHED, "datetime.utcnow()-timedelta(seconds=75)"),
                (RunningState.PUBLISHED, "datetime.utcnow()-timedelta(seconds=155)"),
            ],
            RunningState.PUBLISHED,
        ),
        (
            # pipeline is published if any of the node is published AND time is within publication timeout
            [
                (
                    RunningState.PUBLISHED,
                    "datetime.utcnow()-timedelta(seconds=CELERY_PUBLICATION_TIMEOUT + 75)",
                ),
                (RunningState.PUBLISHED, "datetime.utcnow()-timedelta(seconds=145)"),
                (RunningState.PUBLISHED, "datetime.utcnow()-timedelta(seconds=1555)"),
            ],
            RunningState.NOT_STARTED,
        ),
        (
            # not started pipeline (all nodes are in non started mode)
            [
                (
                    RunningState.NOT_STARTED,
                    "fake.date_time()",
                ),
                (
                    RunningState.NOT_STARTED,
                    "fake.date_time()",
                ),
            ],
            RunningState.NOT_STARTED,
        ),
        (
            # successful pipeline if ALL of the node are successful
            [
                (RunningState.SUCCESS, "fake.date_time()"),
                (RunningState.SUCCESS, "fake.date_time()"),
            ],
            RunningState.SUCCESS,
        ),
        (
            # pending pipeline if ALL of the node are pending
            [
                (RunningState.PENDING, "fake.date_time()"),
                (RunningState.PENDING, "fake.date_time()"),
            ],
            RunningState.PENDING,
        ),
        (
            # failed pipeline if any of the node is failed
            [
                (RunningState.PENDING, "fake.date_time()"),
                (RunningState.FAILED, "fake.date_time()"),
                (RunningState.PENDING, "fake.date_time()"),
            ],
            RunningState.FAILED,
        ),
        (
            # started pipeline if any of the node is started
            [
                (RunningState.STARTED, "fake.date_time()"),
                (RunningState.FAILED, "fake.date_time()"),
            ],
            RunningState.FAILED,
        ),
        (
            # started pipeline if any of the node is started
            [
                (RunningState.SUCCESS, "fake.date_time()"),
                (RunningState.PENDING, "fake.date_time()"),
                (RunningState.PENDING, "fake.date_time()"),
            ],
            RunningState.STARTED,
        ),
        (
            # ABORTED pipeline if any of the node is aborted
            [
                (RunningState.SUCCESS, "fake.date_time()"),
                (RunningState.ABORTED, "fake.date_time()"),
                (RunningState.PENDING, "fake.date_time()"),
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
    configure_celery_timeout,
    task_states: List[RunningState],
    exp_pipeline_state: RunningState,
    fake_task: CompTaskAtDB,
    publication_timeout: int,
):
    tasks: List[CompTaskAtDB] = [
        fake_task.copy(deep=True, update={"state": s, "submit": _lazy_evaluate_time(t)})
        for s, t in task_states
    ]

    pipeline_state: RunningState = get_pipeline_state_from_task_states(
        tasks, publication_timeout
    )
    assert (
        pipeline_state == exp_pipeline_state
    ), f"task states are: {task_states}, got {pipeline_state} instead of {exp_pipeline_state}"
