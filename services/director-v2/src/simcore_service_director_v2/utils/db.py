import json
from typing import Any

from fastapi import FastAPI
from models_library.clusters import BaseCluster
from models_library.projects_state import RunningState
from settings_library.utils_cli import create_json_encoder_wo_secrets
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
}

RUNNING_STATE_TO_DB = {
    **{v: k for k, v in DB_TO_RUNNING_STATE.items()},
    RunningState.RETRY: StateType.RUNNING,
    RunningState.WAITING_FOR_RESOURCES: StateType.PENDING,
}


def to_clusters_db(cluster: BaseCluster, *, only_update: bool) -> dict[str, Any]:
    db_model: dict[str, Any] = json.loads(
        cluster.json(
            by_alias=True,
            exclude={"id", "access_rights"},
            exclude_unset=only_update,
            exclude_none=only_update,
            encoder=create_json_encoder_wo_secrets(BaseCluster),
        )
    )
    return db_model


def get_repository(app: FastAPI, repo_type: type[RepoType]) -> RepoType:
    return get_base_repository(engine=app.state.engine, repo_type=repo_type)
