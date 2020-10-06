""" Interface to other subsystems

    - Data validation
    - Operations on projects
        - are NOT handlers, therefore do not return web.Response
        - return data and successful HTTP responses (or raise them)
        - upon failure raise errors that can be also HTTP reponses
"""
# pylint: disable=too-many-arguments

import logging
from pprint import pformat
from typing import Any, Dict, Optional, Set
from uuid import uuid4

from aiohttp import web

from models_library.projects import (
    Owner,
    ProjectLocked,
    ProjectRunningState,
    ProjectState,
)
from servicelib.application_keys import APP_JSONSCHEMA_SPECS_KEY
from servicelib.jsonschema_validation import validate_instance
from servicelib.observer import observe
from servicelib.utils import fire_and_forget_task, logged_gather

from ..computation_api import delete_pipeline_db, get_pipeline_state
from ..director import director_api
from ..resource_manager.websocket_manager import managed_resource
from ..socketio.events import SOCKET_IO_PROJECT_UPDATED_EVENT, post_group_messages
from ..storage_api import copy_data_folders_from_project  # mocked in unit-tests
from ..storage_api import (
    delete_data_folders_of_project,
    delete_data_folders_of_project_node,
)
from ..users_api import get_user_name
from .config import CONFIG_SECTION_NAME
from .projects_db import APP_PROJECT_DBAPI
from .projects_exceptions import NodeNotFoundError
from .projects_utils import clone_project_document

log = logging.getLogger(__name__)


def _is_node_dynamic(node_key: str) -> bool:
    return "/dynamic/" in node_key


def validate_project(app: web.Application, project: Dict):
    project_schema = app[APP_JSONSCHEMA_SPECS_KEY][CONFIG_SECTION_NAME]
    validate_instance(project, project_schema)  # TODO: handl


async def get_project_for_user(
    app: web.Application,
    project_uuid: str,
    user_id: int,
    *,
    include_templates: bool = False,
    include_state: bool = False,
) -> Dict:
    """Returns a VALID project accessible to user

    :raises web.HTTPNotFound: if no match found
    :return: schema-compliant project data
    :rtype: Dict
    """
    db = app[APP_PROJECT_DBAPI]

    is_template = False
    if include_templates:
        project = await db.get_template_project(project_uuid)
        is_template = bool(project)

    if not is_template:
        project = await db.get_user_project(user_id, project_uuid)

    # adds state if it is not a template
    if include_state:
        project_state = await get_project_state_for_user(user_id, project_uuid, app)
        project["state"] = project_state.dict(by_alias=True, exclude_unset=True)

    # TODO: how to handle when database has an invalid project schema???
    # Notice that db model does not include a check on project schema.
    validate_project(app, project)
    return project


async def clone_project(
    request: web.Request, project: Dict, user_id: int, forced_copy_project_id: str = ""
) -> Dict:
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

    updated_project = await copy_data_folders_from_project(
        request.app, project, cloned_project, nodes_map, user_id
    )

    return updated_project


async def start_project_interactive_services(
    request: web.Request, project: Dict, user_id: str
) -> None:
    # first get the services if they already exist
    log.debug(
        "getting running interactive services of project %s for user %s",
        project["uuid"],
        user_id,
    )
    running_services = await director_api.get_running_interactive_services(
        request.app, user_id, project["uuid"]
    )
    log.debug("Running services %s", running_services)

    running_service_uuids = [x["service_uuid"] for x in running_services]
    # now start them if needed
    project_needed_services = {
        service_uuid: service
        for service_uuid, service in project["workbench"].items()
        if _is_node_dynamic(service["key"])
        and service_uuid not in running_service_uuids
    }
    log.debug("Services to start %s", project_needed_services)

    start_service_tasks = [
        director_api.start_service(
            request.app,
            user_id=user_id,
            project_id=project["uuid"],
            service_key=service["key"],
            service_version=service["version"],
            service_uuid=service_uuid,
        )
        for service_uuid, service in project_needed_services.items()
    ]

    result = await logged_gather(*start_service_tasks, reraise=True)
    log.debug("Services start result %s", result)
    for entry in result:
        # if the status is present in the results fo the start_service
        # it means that the API call failed
        # also it is enforced that the status is different from 200 OK
        if "status" not in entry:
            continue

        if entry["status"] != 200:
            log.error("Error while starting dynamic service %s", entry)


async def delete_project(request: web.Request, project_uuid: str, user_id: int) -> None:
    await delete_project_from_db(request.app, project_uuid, user_id)

    async def remove_services_and_data():
        await remove_project_interactive_services(user_id, project_uuid, request.app)
        await delete_project_data(request, project_uuid, user_id)

    fire_and_forget_task(remove_services_and_data())


@observe(event="SIGNAL_PROJECT_CLOSE")
async def remove_project_interactive_services(
    user_id: Optional[int], project_uuid: Optional[str], app: web.Application
) -> None:
    if not user_id and not project_uuid:
        raise ValueError("Expected either user or project")

    list_of_services = await director_api.get_running_interactive_services(
        app, project_id=project_uuid, user_id=user_id
    )
    stop_tasks = [
        director_api.stop_service(app, service["service_uuid"])
        for service in list_of_services
    ]
    if stop_tasks:
        await logged_gather(*stop_tasks, reraise=False)


async def delete_project_data(
    request: web.Request, project_uuid: str, user_id: int
) -> None:
    # requests storage to delete all project's stored data
    await delete_data_folders_of_project(request.app, project_uuid, user_id)


async def delete_project_from_db(
    app: web.Application, project_uuid: str, user_id: int
) -> None:
    db = app[APP_PROJECT_DBAPI]
    await delete_pipeline_db(app, project_uuid)
    await db.delete_user_project(user_id, project_uuid)
    # requests storage to delete all project's stored data
    await delete_data_folders_of_project(app, project_uuid, user_id)


async def add_project_node(
    request: web.Request,
    project_uuid: str,
    user_id: int,
    service_key: str,
    service_version: str,
    service_id: Optional[str],
) -> str:
    log.debug(
        "starting node %s:%s in project %s for user %s",
        service_key,
        service_version,
        project_uuid,
        user_id,
    )
    node_uuid = service_id if service_id else str(uuid4())
    if _is_node_dynamic(service_key):
        await director_api.start_service(
            request.app, user_id, project_uuid, service_key, service_version, node_uuid
        )
    return node_uuid


async def get_project_node(
    request: web.Request, project_uuid: str, user_id: int, node_id: str
):
    log.debug(
        "getting node %s in project %s for user %s", node_id, project_uuid, user_id
    )

    list_of_interactive_services = await director_api.get_running_interactive_services(
        request.app, project_id=project_uuid, user_id=user_id
    )
    # get the project if it is running
    for service in list_of_interactive_services:
        if service["service_uuid"] == node_id:
            return service
    # the service is not running, it's a computational service maybe
    # TODO: find out if computational service is running if not throw a 404 since it's not around
    return {"service_uuid": node_id, "service_state": "idle"}


async def delete_project_node(
    request: web.Request, project_uuid: str, user_id: int, node_uuid: str
) -> None:
    log.debug(
        "deleting node %s in project %s for user %s", node_uuid, project_uuid, user_id
    )

    list_of_services = await director_api.get_running_interactive_services(
        request.app, project_id=project_uuid, user_id=user_id
    )
    # stop the service if it is running
    for service in list_of_services:
        if service["service_uuid"] == node_uuid:
            await director_api.stop_service(request.app, node_uuid)
            break
    # remove its data if any
    await delete_data_folders_of_project_node(
        request.app, project_uuid, node_uuid, user_id
    )


async def update_project_node_progress(
    app: web.Application, user_id: int, project_id: str, node_id: str, progress: float
) -> Optional[Dict]:
    log.debug(
        "updating node %s progress in project %s for user %s with %s",
        node_id,
        project_id,
        user_id,
        progress,
    )
    project = await get_project_for_user(app, project_id, user_id)
    if not node_id in project["workbench"]:
        raise NodeNotFoundError(project_id, node_id)

    project["workbench"][node_id]["progress"] = int(100.0 * float(progress) + 0.5)
    db = app[APP_PROJECT_DBAPI]
    await db.update_user_project(project, user_id, project_id)
    return project["workbench"][node_id]


async def update_project_node_outputs(
    app: web.Application,
    user_id: int,
    project_id: str,
    node_id: str,
    data: Optional[Dict],
) -> Dict:
    """
    Updates outputs of a given node in a project with 'data'
    """
    log.debug(
        "updating node %s outputs in project %s for user %s with %s",
        node_id,
        project_id,
        user_id,
        pformat(data),
    )
    data: Dict[str, Any] = data or {}
    project = await get_project_for_user(app, project_id, user_id)

    if not node_id in project["workbench"]:
        raise NodeNotFoundError(project_id, node_id)

    if data:
        # NOTE: update outputs (not required) if necessary as the UI expects a
        # dataset/label field that is missing
        outputs: Dict[str, Any] = project["workbench"][node_id].setdefault(
            "outputs", {}
        )
        outputs.update(data)

        for output_key in outputs.keys():
            if not isinstance(outputs[output_key], dict):
                continue
            if "path" in outputs[output_key]:
                # file_id is of type study_id/node_id/file.ext
                file_id = outputs[output_key]["path"]
                study_id, _, file_ext = file_id.split("/")
                outputs[output_key]["dataset"] = study_id
                outputs[output_key]["label"] = file_ext

        db = app[APP_PROJECT_DBAPI]
        await db.update_user_project(project, user_id, project_id)
    return project["workbench"][node_id]


async def get_workbench_node_ids_from_project_uuid(
    app: web.Application,
    project_uuid: str,
) -> Set[str]:
    """Returns a set with all the node_ids from a project's workbench"""
    db = app[APP_PROJECT_DBAPI]
    return await db.get_all_node_ids_from_workbenches(project_uuid)


async def is_node_id_present_in_any_project_workbench(
    app: web.Application,
    node_id: str,
) -> bool:
    """If the node_id is presnet in one of the projects' workbenche returns True"""
    db = app[APP_PROJECT_DBAPI]
    return node_id in await db.get_all_node_ids_from_workbenches()


async def notify_project_state_update(app: web.Application, project: Dict) -> None:
    rooms_to_notify = [
        f"{gid}" for gid, rights in project["accessRights"].items() if rights["read"]
    ]

    messages = {
        SOCKET_IO_PROJECT_UPDATED_EVENT: {
            "project_uuid": project["uuid"],
            "data": project["state"],
        }
    }

    for room in rooms_to_notify:
        await post_group_messages(app, room, messages)


async def _get_project_lock_state(
    user_id: int, project_uuid: str, app: web.Application
) -> ProjectLocked:
    with managed_resource(user_id, None, app) as rt:
        # checks who is using it
        users_of_project = await rt.find_users_of_resource("project_id", project_uuid)
        usernames = [await get_user_name(app, uid) for uid in set(users_of_project)]
        assert len(usernames) <= 1  # currently not possible to have more than 1

        # based on usage, sets an state
        is_locked: bool = len(usernames) > 0
        if is_locked:
            return ProjectLocked(
                value=is_locked,
                owner=Owner(**usernames[0]),
            )
        return ProjectLocked(value=is_locked)


async def _get_project_running_state(
    project_uuid: str, app: web.Application
) -> ProjectRunningState:
    pipeline_state = await get_pipeline_state(app, project_uuid)
    return ProjectRunningState(value=pipeline_state)


async def get_project_state_for_user(user_id, project_uuid, app) -> ProjectState:
    """
    Returns state of a project with respect to a given user
    E.g.
        the state is locked for user1 because user2 is working on it and
        there is a locked-while-using policy in place

    WARNING: assumes project_uuid exists!! If not, call first get_project_for_user
    NOTE: This adds a dependency to the socket registry sub-module. Many tests
        might require a mock for this function to work properly
    """
    lock_state = await _get_project_lock_state(user_id, project_uuid, app)
    running_state = await _get_project_running_state(project_uuid, app)
    return ProjectState(
        locked=lock_state,
        state=running_state,
    )
