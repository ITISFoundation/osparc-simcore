import json
import logging
from typing import Any, Final

from fastapi import FastAPI
from models_library.clusters import BaseCluster
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID, NodeIDStr
from models_library.projects_state import RunningState
from settings_library.utils_cli import create_json_encoder_wo_secrets
from simcore_postgres_database.models.comp_pipeline import StateType
from simcore_postgres_database.utils_projects_metadata import DBProjectNotFoundError

from ..api.dependencies.database import RepoType, get_base_repository
from ..core.errors import ProjectNotFoundError
from ..models.comp_runs import ProjectMetadataDict
from ..modules.db.repositories.projects import ProjectsRepository
from ..modules.db.repositories.projects_metadata import ProjectsMetadataRepository

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


_UNKNOWN_NODE: Final[str] = "unknown node"


async def get_project_metadata(
    project_id: ProjectID,
    project_repo: ProjectsRepository,
    projects_metadata_repo: ProjectsMetadataRepository,
) -> ProjectMetadataDict:
    try:
        project_ancestors = await projects_metadata_repo.get_project_ancestors(
            project_id
        )
        if project_ancestors.parent_project_uuid is None:
            # no parents here
            return {}

        assert project_ancestors.parent_node_id is not None  # nosec
        assert project_ancestors.root_project_uuid is not None  # nosec
        assert project_ancestors.root_node_id is not None  # nosec

        async def _get_project_node_names(
            project_uuid: ProjectID, node_id: NodeID
        ) -> tuple[str, str]:
            prj = await project_repo.get_project(project_uuid)
            node_id_str = NodeIDStr(f"{node_id}")
            if node_id_str not in prj.workbench:
                _logger.error(
                    "%s not found in %s. it is an ancestor of %s. Please check!",
                    f"{node_id=}",
                    f"{prj.uuid=}",
                    f"{project_id=}",
                )
                return prj.name, _UNKNOWN_NODE
            return prj.name, prj.workbench[node_id_str].label

        parent_project_name, parent_node_name = await _get_project_node_names(
            project_ancestors.parent_project_uuid, project_ancestors.parent_node_id
        )
        root_parent_project_name, root_parent_node_name = await _get_project_node_names(
            project_ancestors.root_project_uuid, project_ancestors.root_node_id
        )
        return ProjectMetadataDict(
            parent_node_id=project_ancestors.parent_node_id,
            parent_node_name=parent_node_name,
            parent_project_id=project_ancestors.parent_project_uuid,
            parent_project_name=parent_project_name,
            root_parent_node_id=project_ancestors.root_node_id,
            root_parent_node_name=root_parent_node_name,
            root_parent_project_id=project_ancestors.root_project_uuid,
            root_parent_project_name=root_parent_project_name,
        )

    except DBProjectNotFoundError:
        _logger.exception("Could not find project: %s", f"{project_id=}")
    except ProjectNotFoundError as exc:
        _logger.exception("Could not find parent project: %s", f"{exc.project_id=}")

    return {}
