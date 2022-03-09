""" Core submodule: logic to get a project resource
"""

import asyncio
import logging
from typing import Optional

from aiohttp import web
from servicelib.aiohttp.application_keys import APP_JSONSCHEMA_SPECS_KEY
from servicelib.aiohttp.jsonschema_validation import validate_instance

from ._core_states import add_project_states_for_user
from .project_models import ProjectDict
from .projects_db import APP_PROJECT_DBAPI, ProjectDBAPI

log = logging.getLogger(__name__)


async def validate_project(app: web.Application, project: ProjectDict):
    """
    raises ProjectValidationError
    """
    project_schema = app[APP_JSONSCHEMA_SPECS_KEY]["projects"]
    await asyncio.get_event_loop().run_in_executor(
        None, validate_instance, project, project_schema
    )


async def get_project_for_user(
    app: web.Application,
    project_uuid: str,
    user_id: int,
    *,
    include_templates: Optional[bool] = False,
    include_state: Optional[bool] = False,
) -> ProjectDict:
    """Returns a VALID project accessible to user

    :raises ProjectNotFoundError: if no match found
    """
    db: ProjectDBAPI = app[APP_PROJECT_DBAPI]
    assert db  # nosec

    project: ProjectDict = {}
    is_template = False
    if include_templates:
        project = await db.get_template_project(project_uuid)
        is_template = bool(project)

    if not project:
        project = await db.get_user_project(user_id, project_uuid)

    # adds state if it is not a template
    if include_state:
        project = await add_project_states_for_user(user_id, project, is_template, app)

    # TODO: how to handle when database has an invalid project schema???
    # Notice that db model does not include a check on project schema.
    await validate_project(app, project)
    return project


# NOTE: Needs refactoring after access-layer in storage. DO NOT USE but keep
#       here since it documents well the concept
#
# async def clone_project(
#     request: web.Request, project: Dict, user_id: int, forced_copy_project_id: str = ""
# ) -> Dict:
#     """Clones both document and data folders of a project
#
#     - document
#         - get new identifiers for project and nodes
#     - data folders
#         - folder name composes as project_uuid/node_uuid
#         - data is deep-copied to new folder corresponding to new identifiers
#         - managed by storage uservice
#     """
#     cloned_project, nodes_map = clone_project_document(project, forced_copy_project_id)
#
#     updated_project = await copy_data_folders_from_project(
#         request.app, project, cloned_project, nodes_map, user_id
#     )
#
#     return updated_project
