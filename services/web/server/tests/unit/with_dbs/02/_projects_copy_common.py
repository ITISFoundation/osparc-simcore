# pylint: disable=protected-access
# pylint: disable=redefined-outer-name

"""Helpers shared by `test_projects_service__copy.py` and
`test_projects_service__copy_pricing.py`.
"""

from aiohttp import web
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from models_library.users import UserID
from simcore_postgres_database.utils_projects_nodes import ProjectNode
from simcore_service_webserver.projects import _projects_service
from simcore_service_webserver.projects._projects_repository_legacy import ProjectDBAPI
from simcore_service_webserver.projects.models import ProjectDict


async def _get_inserted_nodes(app: web.Application, project_uuid: str) -> dict[NodeID, ProjectNode]:
    db: ProjectDBAPI = ProjectDBAPI.get_from_app_context(app)
    return {node.node_id: node for node in await db.list_project_nodes(ProjectID(project_uuid))}


async def _fetch_source_project(app: web.Application, project_uuid: str, user_id: UserID) -> ProjectDict:
    """Fetches a project the same way `_prepare_project_copy` does in `_crud_api_create.py`.

    NOTE: the `user_project`/`template_project` fixtures return a test-helper-only
    dict shape (e.g. with a `trashedAt` key that doesn't round-trip through
    `convert_to_db_names`). Real callers of `clone_project_data` always obtain
    `source_project` via `get_project_for_user`, so tests do the same.
    """
    return await _projects_service.get_project_for_user(app, project_uuid=project_uuid, user_id=user_id)
