from typing import TypeVar

from aiopg.sa.engine import Engine
from models_library.projects_state import RunningState
from pydantic import PositiveInt

SCHEDULED_STATES: set[RunningState] = {
    RunningState.PUBLISHED,
    RunningState.PENDING,
    RunningState.STARTED,
    RunningState.RETRY,
}

WAITING_FOR_START_STATES: set[RunningState] = {
    RunningState.PUBLISHED,
    RunningState.PENDING,
    RunningState.RETRY,
}

PROCESSING_STATES: set[RunningState] = {
    RunningState.PENDING,
    RunningState.STARTED,
}

COMPLETED_STATES: set[RunningState] = {
    RunningState.ABORTED,
    RunningState.SUCCESS,
    RunningState.FAILED,
    RunningState.UNKNOWN,
}

RepoType = TypeVar("RepoType")


def get_repository(db_engine: Engine, repo_cls: type[RepoType]) -> RepoType:
    return repo_cls(db_engine=db_engine)


Iteration = PositiveInt
