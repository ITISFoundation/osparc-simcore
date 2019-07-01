""" Interface to other subsystems

    - Data validation
    - Operations on projects
        - are NOT handlers, therefore do not return web.Response
        - return data and successful HTTP responses (or raise them)
        - upon failure raise errors that can be also HTTP reponses
"""
from typing import Dict

from aiohttp import web

from servicelib.application_keys import APP_JSONSCHEMA_SPECS_KEY
from servicelib.jsonschema_validation import validate_instance

from ..security_api import check_permission
from .config import CONFIG_SECTION_NAME
from .projects_db import APP_PROJECT_DBAPI
from .projects_exceptions import ProjectNotFoundError


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
