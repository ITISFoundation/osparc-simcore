""" Interface to other subsystems

    - Data validation
    - Operations on projects
        - are NOT handlers, therefore do not return web.Response
        - return data and successful HTTP responses (or raise them)
        - upon failure raise errors that can be also HTTP reponses
"""
import uuid as uuidlib
from copy import deepcopy
from typing import Dict

from aiohttp import web

from servicelib.application_keys import APP_JSONSCHEMA_SPECS_KEY
from servicelib.jsonschema_validation import validate_instance

from ..security_api import check_permission
from .config import CONFIG_SECTION_NAME
from .projects_db import APP_PROJECT_DBAPI
from .projects_exceptions import ProjectNotFoundError
from .projects_fakes import Fake

BASE_UUID = uuidlib.UUID("71e0eb5e-0797-4469-89ba-00a0df4d338a")
TEMPLATE_PREFIX = "template-uuid"


def _compose_uuid(template_uuid, user_id) -> str:
    """ Creates a new uuid composing a project's and user ids such that
        any template pre-assigned to a user

        LIMITATION: a user cannot have multiple copies of the same template
        TODO: cache results
    """
    new_uuid = str( uuidlib.uuid5(BASE_UUID, str(template_uuid) + str(user_id)) )
    return new_uuid


def validate_project(app: web.Application, project: Dict):
    project_schema = app[APP_JSONSCHEMA_SPECS_KEY][CONFIG_SECTION_NAME]
    validate_instance(project, project_schema) # TODO: handl


async def get_project_for_user(request: web.Request, project_uuid, user_id) -> Dict:
    await check_permission(request, "project.read")

    if project_uuid in Fake.projects:
        return Fake.projects[project_uuid].data

    try:
        db = request.config_dict[APP_PROJECT_DBAPI]
        project = await db.get_user_project(user_id, project_uuid)

        # TODO: how to handle when database has an invalid project schema???
        validate_project(request.app, project)
        return project

    except ProjectNotFoundError:
        raise web.HTTPNotFound(reason="Project not found")


def create_data_from_template(template_project: Dict, user_id: int) -> Dict:
    """ Formats template and prepares it for a standard project

    - Replaces all uuids marked with TEMPLATE_PREFIX

    :param template_project: schema-compatible template
    :type template_project: Dict
    :param user_id: user db identifier
    :type user_id: int
    :return: schema-compatible project data
    :rtype: Dict
    """
    def _replace_uuids(node):
        if isinstance(node, str):
            if node.startswith(TEMPLATE_PREFIX):
                node = _compose_uuid(node, user_id)
        elif isinstance(node, list):
            node = [_replace_uuids(item) for item in node]
        elif isinstance(node, dict):
            _frozen_items = tuple(node.items())
            for key, value in _frozen_items:
                if isinstance(key, str):
                    if key.startswith(TEMPLATE_PREFIX):
                        new_key = _compose_uuid(key, user_id)
                        node[new_key] = node.pop(key)
                        key = new_key
                node[key] = _replace_uuids(value)
        return node

    project = deepcopy(template_project)
    project = _replace_uuids(project)

    return project
