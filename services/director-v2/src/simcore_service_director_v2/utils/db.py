import logging
from typing import Any

from common_library.serialization import model_dump_with_secrets
from fastapi import FastAPI
from models_library.clusters import BaseCluster
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
}

RUNNING_STATE_TO_DB = {v: k for k, v in DB_TO_RUNNING_STATE.items()} | {
    RunningState.UNKNOWN: StateType.FAILED
}

_logger = logging.getLogger(__name__)


def to_clusters_db(cluster: BaseCluster, *, only_update: bool) -> dict[str, Any]:
    db_model: dict[str, Any] = model_dump_with_secrets(
        cluster,
        show_secrets=True,
        by_alias=True,
        exclude={"id", "access_rights"},
        exclude_unset=only_update,
        exclude_none=only_update,
    )
    return db_model


def get_repository(app: FastAPI, repo_type: type[RepoType]) -> RepoType:
    return get_base_repository(engine=app.state.engine, repo_type=repo_type)
