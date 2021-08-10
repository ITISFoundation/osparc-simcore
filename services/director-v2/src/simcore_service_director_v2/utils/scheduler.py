from typing import Set, Type

from aiopg.sa.engine import Engine
from models_library.projects_state import RunningState
from pydantic import PositiveInt

from ..modules.db.repositories import BaseRepository

SCHEDULED_STATES: Set[RunningState] = {
    RunningState.PUBLISHED,
    RunningState.PENDING,
    RunningState.STARTED,
    RunningState.RETRY,
}

COMPLETED_STATES: Set[RunningState] = {
    RunningState.ABORTED,
    RunningState.SUCCESS,
    RunningState.FAILED,
}


def get_repository(db_engine: Engine, repo_cls: Type[BaseRepository]) -> BaseRepository:
    return repo_cls(db_engine=db_engine)


Iteration = PositiveInt
