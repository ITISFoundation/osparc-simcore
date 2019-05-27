""" Interface to other subsystems

    - Data validation
    - Operations on projects
        - are NOT handlers, therefore do not return web.Response
        - return data and successful HTTP responses (or raise them)
        - upon failure raise errors that can be also HTTP reponses
"""
from typing import Dict

from aiohttp import web

from servicelib.application_keys import (APP_DB_ENGINE_KEY,
                                         APP_JSONSCHEMA_SPECS_KEY)
from servicelib.jsonschema_validation import validate_instance

from ..security_api import check_permission
from .config import CONFIG_SECTION_NAME
from .projects_exceptions import ProjectNotFoundError
from .projects_fakes import Fake
from .projects_models import ProjectDB


def validate_project(app: web.Application, project: Dict):
    project_schema = app[APP_JSONSCHEMA_SPECS_KEY][CONFIG_SECTION_NAME]
    validate_instance(project, project_schema) # TODO: handl


async def get_project_for_user(request: web.Request, project_uuid, user_id) -> Dict:
    await check_permission(request, "project.read")

    if project_uuid in Fake.projects:
        return Fake.projects[project_uuid].data

    try:
        db = request.config_dict[APP_DB_ENGINE_KEY]
        project = await ProjectDB.get_user_project(user_id, project_uuid, db_engine=db)

        # TODO: how to handle when database has an invalid project schema???
        validate_project(request.app, project)
        return project

    except ProjectNotFoundError:
        raise web.HTTPNotFound(reason="Project not found")
