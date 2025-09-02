import logging

from fastapi import FastAPI
from models_library.projects_state import RunningState
from simcore_postgres_database.models.comp_pipeline import StateType

from ..api.dependencies.database import RepoType, get_base_repository

DB_TO_RUNNING_STATE = {
    StateType.FAILED: RunningState.FAILED,
    StateType.PENDING: RunningState.PENDING,
    StateType.SUCCESS: RunningState.SUCCESS,
    StateType.PUBLISHED: RunningState.PUBLISHED,
    StateType.NOT_STARTED: RunningState.NOT_STARTED,
    StateType.RUNNING: RunningState.STARTED,
    StateType.ABORTED: RunningState.ABORTED,
    StateType.WAITING_FOR_RESOURCES: RunningState.WAITING_FOR_RESOURCES,
    StateType.WAITING_FOR_CLUSTER: RunningState.WAITING_FOR_CLUSTER,
    StateType.UNKNOWN: RunningState.UNKNOWN,
}

RUNNING_STATE_TO_DB = {v: k for k, v in DB_TO_RUNNING_STATE.items()}

_logger = logging.getLogger(__name__)


def get_repository(app: FastAPI, repo_type: type[RepoType]) -> RepoType:
    return get_base_repository(engine=app.state.engine, repo_type=repo_type)
