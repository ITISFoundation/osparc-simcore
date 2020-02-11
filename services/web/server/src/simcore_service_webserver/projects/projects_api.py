""" Interface to other subsystems

    - Data validation
    - Operations on projects
        - are NOT handlers, therefore do not return web.Response
        - return data and successful HTTP responses (or raise them)
        - upon failure raise errors that can be also HTTP reponses
"""
import logging
from asyncio import ensure_future, gather
from pprint import pprint
from typing import Dict, Optional
from uuid import uuid4

from aiohttp import web

from servicelib.application_keys import APP_JSONSCHEMA_SPECS_KEY
from servicelib.jsonschema_validation import validate_instance
from servicelib.observer import observe

from ..computation_api import delete_pipeline_db
from ..director import director_api
from ..storage_api import \
    copy_data_folders_from_project  # mocked in unit-tests
from ..storage_api import (delete_data_folders_of_project,
                           delete_data_folders_of_project_node)
from .config import CONFIG_SECTION_NAME
from .projects_db import APP_PROJECT_DBAPI
from .projects_exceptions import NodeNotFoundError, ProjectNotFoundError
from .projects_utils import clone_project_document

log = logging.getLogger(__name__)

def _is_node_dynamic(node_key: str) -> bool:
    return "/dynamic/" in node_key

def validate_project(app: web.Application, project: Dict):
    project_schema = app[APP_JSONSCHEMA_SPECS_KEY][CONFIG_SECTION_NAME]
    validate_instance(project, project_schema) # TODO: handl


async def get_project_for_user(app: web.Application, project_uuid, user_id, *, include_templates=False) -> Dict:
    """ Returns a project accessible to user

    :raises web.HTTPNotFound: if no match found
    :return: schema-compliant project data
    :rtype: Dict
    """

    try:
        db = app[APP_PROJECT_DBAPI]

        project = None
        if include_templates:
            project = await db.get_template_project(project_uuid)

        if not project:
            project = await db.get_user_project(user_id, project_uuid)

        # TODO: how to handle when database has an invalid project schema???
        # Notice that db model does not include a check on project schema.
        validate_project(app, project)
        return project

    except ProjectNotFoundError:
        raise web.HTTPNotFound(reason="Project not found")


async def clone_project(request: web.Request, project: Dict, user_id, forced_copy_project_id: str ="") -> Dict:
    """Clones both document and data folders of a project

    - document
        - get new identifiers for project and nodes
    - data folders
        - folder name composes as project_uuid/node_uuid
        - data is deep-copied to new folder corresponding to new identifiers
        - managed by storage uservice

    TODO: request to application

    :param request: http request
    :type request: web.Request
    :param project: source project document
    :type project: Dict
    :return: project document with updated data links
    :rtype: Dict
    """
    cloned_project, nodes_map = clone_project_document(project, forced_copy_project_id)

    updated_project = await copy_data_folders_from_project(request.app,
        project, cloned_project, nodes_map, user_id)

    return updated_project

async def start_project_interactive_services(request: web.Request, project: Dict, user_id: str) -> None:
    # first get the services if they already exist
    log.debug("getting running interactive services of project %s for user %s", project["uuid"], user_id)
    running_services = await director_api.get_running_interactive_services(request.app, user_id, project["uuid"])
    running_service_uuids = [x["service_uuid"] for x in running_services]
    # now start them if needed
    project_needed_services = {service_uuid:service for service_uuid, service in project["workbench"].items() \
                                    if _is_node_dynamic(service["key"]) and \
                                        service_uuid not in running_service_uuids}

    start_service_tasks = [director_api.start_service(request.app,
                            user_id=user_id,
                            project_id=project["uuid"],
                            service_key=service["key"],
                            service_version=service["version"],
                            service_uuid=service_uuid) for service_uuid, service in project_needed_services.items()]
    await gather(*start_service_tasks)


async def delete_project(request: web.Request, project_uuid: str, user_id: str) -> None:
    await delete_project_from_db(request, project_uuid, user_id)
    async def remove_services_and_data():
        await remove_project_interactive_services(user_id, project_uuid, request.app)
        await delete_project_data(request, project_uuid, user_id)
    ensure_future(remove_services_and_data())

@observe(event="SIGNAL_PROJECT_CLOSE")
async def remove_project_interactive_services(user_id: Optional[str], project_uuid: Optional[str], app: web.Application) -> None:
    assert user_id or project_uuid
    list_of_services = await director_api.get_running_interactive_services(app,
                                                                            project_id=project_uuid,
                                                                            user_id=user_id)
    stop_tasks = [director_api.stop_service(app, service["service_uuid"]) for service in list_of_services]
    if stop_tasks:
        await gather(*stop_tasks)

async def delete_project_data(request: web.Request, project_uuid: str, user_id: str) -> None:
    # requests storage to delete all project's stored data
    await delete_data_folders_of_project(request.app, project_uuid, user_id)

async def delete_project_from_db(request: web.Request, project_uuid: str, user_id: str) -> None:
    db = request.config_dict[APP_PROJECT_DBAPI]
    try:
        await delete_pipeline_db(request.app, project_uuid)
        await db.delete_user_project(user_id, project_uuid)
    except ProjectNotFoundError:
        # TODO: add flag in query to determine whether to respond if error?
        raise web.HTTPNotFound

    # requests storage to delete all project's stored data
    await delete_data_folders_of_project(request.app, project_uuid, user_id)

async def add_project_node(request: web.Request, project_uuid: str, user_id: str, service_key: str, service_version: str, service_id: Optional[str]) -> str: # pylint: disable=too-many-arguments
    log.debug("starting node %s:%s in project %s for user %s", service_key, service_version, project_uuid, user_id)
    node_uuid = service_id if service_id else str(uuid4())
    if _is_node_dynamic(service_key):
        await director_api.start_service(request.app, user_id, project_uuid, service_key, service_version, node_uuid)
    return node_uuid

async def get_project_node(request: web.Request, project_uuid: str, user_id:str, node_id: str):
    log.debug("getting node %s in project %s for user %s", node_id, project_uuid, user_id)

    list_of_interactive_services = await director_api.get_running_interactive_services(request.app,
                                                                            project_id=project_uuid,
                                                                            user_id=user_id)
    # get the project if it is running
    for service in list_of_interactive_services:
        if service["service_uuid"] == node_id:
            return service
    # the service is not running, it's a computational service maybe
    # TODO: find out if computational service is running if not throw a 404 since it's not around
    return {
        "service_uuid": node_id,
        "service_state": "idle"
    }

async def delete_project_node(request: web.Request, project_uuid: str, user_id: str, node_uuid: str) -> None:
    log.debug("deleting node %s in project %s for user %s", node_uuid, project_uuid, user_id)

    list_of_services = await director_api.get_running_interactive_services(request.app,
                                                                            project_id=project_uuid,
                                                                            user_id=user_id)
    # stop the service if it is running
    for service in list_of_services:
        if service["service_uuid"] == node_uuid:
            await director_api.stop_service(request.app, node_uuid)
            break
    # remove its data if any
    await delete_data_folders_of_project_node(request.app, project_uuid, node_uuid, user_id)


async def update_project_node_progress(app: web.Application, user_id: str, project_id: str, node_id: str, progress: float) -> Optional[Dict]:
    log.debug("updating node %s progress in project %s for user %s with %s", node_id, project_id, user_id, progress)
    project = await get_project_for_user(app, project_id, user_id)
    if not node_id in project["workbench"]:
        raise NodeNotFoundError(project_id, node_id)

    project["workbench"][node_id]["progress"] = int(100.0 * float(progress) + .5)
    db = app[APP_PROJECT_DBAPI]
    await db.update_user_project(project, user_id, project_id)
    return project["workbench"][node_id]

async def update_project_node_outputs(app: web.Application, user_id: str, project_id: str, node_id: str, data: Optional[Dict]) -> Optional[Dict]:
    log.debug("updating node %s outputs in project %s for user %s with %s", node_id, project_id, user_id, pprint(data))
    project = await get_project_for_user(app, project_id, user_id)
    if not node_id in project["workbench"]:
        raise NodeNotFoundError(project_id, node_id)
    node_description = project["workbench"][node_id]
    node_description["outputs"] = data
    # update outputs if necessary
    if node_description["outputs"]:
        for output_key in node_description["outputs"].keys():
            if not isinstance(node_description["outputs"][output_key], dict):
                continue
            if "path" in node_description["outputs"][output_key]:
                # file_id is of type study_id/node_id/file.ext
                file_id = node_description["outputs"][output_key]["path"]
                study_id, _, file_ext = file_id.split("/")
                node_description["outputs"][output_key]["dataset"] = study_id
                node_description["outputs"][output_key]["label"] = file_ext

    db = app[APP_PROJECT_DBAPI]
    await db.update_user_project(project, user_id, project_id)
    return node_description
