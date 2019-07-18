""" Interface to other subsystems

    - Data validation
    - Operations on projects
        - are NOT handlers, therefore do not return web.Response
        - return data and successful HTTP responses (or raise them)
        - upon failure raise errors that can be also HTTP reponses
"""
import logging
from typing import Dict

from aiohttp import web

from servicelib.application_keys import APP_JSONSCHEMA_SPECS_KEY
from servicelib.jsonschema_validation import validate_instance

from ..security_api import check_permission
from ..storage_api import copy_data_from_project # mocked in unit-tests
from .config import CONFIG_SECTION_NAME
from .projects_db import APP_PROJECT_DBAPI
from .projects_exceptions import ProjectNotFoundError
from .projects_utils import clone_project_document

log = logging.getLogger(__name__)

def validate_project(app: web.Application, project: Dict):
    project_schema = app[APP_JSONSCHEMA_SPECS_KEY][CONFIG_SECTION_NAME]
    validate_instance(project, project_schema) # TODO: handl


async def get_project_for_user(request: web.Request, project_uuid, user_id, *, include_templates=False) -> Dict:
    """ Returns a project accessible to user

    :raises web.HTTPNotFound: if no match found
    :return: schema-compliant project data
    :rtype: Dict
    """
    await check_permission(request, "project.read")

    try:
        db = request.config_dict[APP_PROJECT_DBAPI]

        project = None
        if include_templates:
            project = await db.get_template_project(project_uuid)

        if not project:
            project = await db.get_user_project(user_id, project_uuid)

        # TODO: how to handle when database has an invalid project schema???
        # Notice that db model does not include a check on project schema.
        validate_project(request.app, project)
        return project

    except ProjectNotFoundError:
        raise web.HTTPNotFound(reason="Project not found")


async def clone_project(request: web.Request, project: Dict) -> Dict:
    """Clones both document and data in a project

    - Cloned document get new identifiers
    - Data is deep-copied to new location

    :param request: http request
    :type request: web.Request
    :param project: source project document
    :type project: Dict
    :return: project document with updated data links
    :rtype: Dict
    """
    cloned_project, nodes_map = clone_project_document(project)

    updated_project = await copy_data_from_project(request.app, project, cloned_project, nodes_map)

    return updated_project
