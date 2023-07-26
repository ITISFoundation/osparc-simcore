from aiopg.sa.engine import Engine
from models_library.projects_state import RunningState
from pydantic import PositiveInt

from ..api.dependencies.database import RepoType

SCHEDULED_STATES: set[RunningState] = {
    RunningState.PUBLISHED,
    RunningState.PENDING,
    RunningState.WAITING_FOR_RESOURCES,
    RunningState.STARTED,
    RunningState.RETRY,
}

WAITING_FOR_START_STATES: set[RunningState] = {
    RunningState.PUBLISHED,
    RunningState.PENDING,
    RunningState.WAITING_FOR_RESOURCES,
    RunningState.RETRY,
}

PROCESSING_STATES: set[RunningState] = {
    RunningState.PENDING,
    RunningState.WAITING_FOR_RESOURCES,
    RunningState.STARTED,
}

COMPLETED_STATES: set[RunningState] = {
    RunningState.ABORTED,
    RunningState.SUCCESS,
    RunningState.FAILED,
    RunningState.UNKNOWN,
}


def get_repository(db_engine: Engine, repo_cls: type[RepoType]) -> RepoType:
    return repo_cls(db_engine=db_engine)


Iteration = PositiveInt
