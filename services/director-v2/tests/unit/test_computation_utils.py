# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=protected-access


from pathlib import Path
from typing import Dict, List

import pytest
from models_library.projects import NodeID, RunningState
from simcore_service_director_v2.models.domains.comp_tasks import CompTaskAtDB
from simcore_service_director_v2.utils.computations import (
    get_pipeline_state_from_task_states,
)


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


@pytest.mark.parametrize(
    "task_states, exp_pipeline_state",
    [
        (
            [
                (RunningState.PUBLISHED, "datetime.utcnow()"),
                (RunningState.PENDING, "datetime.utcnow()-timedelta(seconds=75)"),
                (RunningState.STARTED, "datetime.utcnow()-timedelta(seconds=155)"),
            ],
            RunningState.NOT_STARTED,
        ),
        (
            [
                (
                    RunningState.PUBLISHED,
                    "datetime.utcnow()-timedelta(seconds=CELERY_PUBLICATION_TIMEOUT + 75)",
                ),
                (RunningState.PENDING, "datetime.utcnow()-timedelta(seconds=145)"),
                (RunningState.STARTED, "datetime.utcnow()-timedelta(seconds=1555)"),
            ],
            RunningState.PUBLISHED,
        ),
    ],
)
def test_get_pipeline_state_from_task_states(
    task_states: List[RunningState],
    exp_pipeline_state: RunningState,
    fake_task: CompTaskAtDB,
    publication_timeout: int,
):
    # pylint: disable=eval-used
    # pylint: disable=unused-import
    from datetime import datetime, timedelta

    tasks: List[CompTaskAtDB] = [
        fake_task.copy(deep=True, update={"state": s, "submit": eval(t)})
        for s, t in task_states
    ]
    import pdb

    pdb.set_trace()
    task_states_dict: Dict[NodeID, CompTaskAtDB] = {t.node_id: t for t in tasks}
    pipeline_state: RunningState = get_pipeline_state_from_task_states(
        task_states_dict, publication_timeout
    )
    assert pipeline_state == exp_pipeline_state
