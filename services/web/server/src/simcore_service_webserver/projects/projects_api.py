""" Interface to other subsystems

    - Data validation
    - Operations on projects
        - are NOT handlers, therefore do not return web.Response
        - return data and successful HTTP responses (or raise them)
        - upon failure raise errors that can be also HTTP reponses
"""
# pylint: disable=too-many-arguments

import json
import logging
from collections import defaultdict
from contextlib import suppress
from pprint import pformat
from typing import Any, Dict, List, Optional, Set, Tuple
from uuid import uuid4

from aiohttp import web
import aioredlock

from models_library.projects_state import (
    Owner,
    ProjectLocked,
    ProjectRunningState,
    ProjectState,
    ProjectStatus,
    RunningState,
)
from servicelib.application_keys import APP_JSONSCHEMA_SPECS_KEY
from servicelib.jsonschema_validation import validate_instance
from servicelib.utils import fire_and_forget_task, logged_gather
from simcore_service_webserver.director import director_exceptions

from ..director import director_api
from ..director_v2 import (
    delete_pipeline,
    get_computation_task,
    request_retrieve_dyn_service,
)
from ..resource_manager.redis import (
    get_redis_lock_manager,
    get_redis_lock_manager_client,
)
from ..resource_manager.websocket_manager import PROJECT_ID_KEY, managed_resource
from ..socketio.events import (
    SOCKET_IO_NODE_UPDATED_EVENT,
    SOCKET_IO_PROJECT_UPDATED_EVENT,
    post_group_messages,
)
from ..storage_api import (
    delete_data_folders_of_project,
    delete_data_folders_of_project_node,
)
from ..users_api import get_user_name, is_user_guest
from .config import CONFIG_SECTION_NAME
from .projects_db import APP_PROJECT_DBAPI

log = logging.getLogger(__name__)

PROJECT_REDIS_LOCK_KEY: str = "project:{}"


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

    project: Dict = {}
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
    validate_project(app, project)
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


async def delete_project(app: web.Application, project_uuid: str, user_id: int) -> None:
    await delete_project_from_db(app, project_uuid, user_id)

    async def remove_services_and_data():
        await remove_project_interactive_services(user_id, project_uuid, app)
        await delete_project_data(app, project_uuid, user_id)

    fire_and_forget_task(remove_services_and_data())


## PROJECT NODES -----------------------------------------------------


async def remove_project_interactive_services_with_notfication(
    user_id: int,
    project_uuid: str,
    app: web.Application,
    project: Dict[str, Any] = None,
) -> None:
    # Note: during the closing process, which might take awhile, the project is locked so no one opens it at the same time
    async with await get_redis_lock_manager(app).lock(
        PROJECT_REDIS_LOCK_KEY.format(project_uuid),
        lock_timeout=None,
        lock_identifier=ProjectLocked(
            value=True,
            owner=Owner(user_id=user_id, **(await get_user_name(app, user_id))),
            status=ProjectStatus.CLOSING,
        ).json(),
    ):
        if project is not None:
            # we notify
            project_with_states = await add_project_states_for_user(
                user_id=user_id,
                project=project,
                is_template=False,
                app=app,
            )
            await notify_project_state_update(app, project_with_states)

        # save the state if the user is not a guest. if we do not know we save in any case.
        with suppress(director_exceptions.DirectorException):
            # here director exceptions are suppressed. in case the service is not found to preserve old behavior
            await director_api.stop_services(
                app=app,
                user_id=user_id,
                project_id=project_uuid,
                save_state=not await is_user_guest(app, user_id) if user_id else True,
            )


async def remove_project_interactive_services(
    user_id: int,
    project_uuid: str,
    app: web.Application,
) -> None:
    return await remove_project_interactive_services_with_notfication(
        user_id, project_uuid, app, None
    )


async def delete_project_data(
    app: web.Application, project_uuid: str, user_id: int
) -> None:
    # requests storage to delete all project's stored data
    await delete_data_folders_of_project(app, project_uuid, user_id)


async def delete_project_from_db(
    app: web.Application, project_uuid: str, user_id: int
) -> None:
    db = app[APP_PROJECT_DBAPI]
    await delete_pipeline(app, user_id, project_uuid)
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
            # no need to save the state of the node when deleting it
            await director_api.stop_service(request.app, node_uuid, save_state=False)
            break
    # remove its data if any
    await delete_data_folders_of_project_node(
        request.app, project_uuid, node_uuid, user_id
    )


async def update_project_node_state(
    app: web.Application, user_id: int, project_id: str, node_id: str, new_state: str
) -> Dict:
    log.debug(
        "updating node %s current state in project %s for user %s",
        node_id,
        project_id,
        user_id,
    )
    partial_workbench_data = {
        node_id: {"state": {"currentStatus": new_state}},
    }
    if RunningState(new_state) in [
        RunningState.PUBLISHED,
        RunningState.PENDING,
        RunningState.STARTED,
    ]:
        partial_workbench_data[node_id]["progress"] = 0
    elif RunningState(new_state) in [RunningState.SUCCESS, RunningState.FAILED]:
        partial_workbench_data[node_id]["progress"] = 100

    db = app[APP_PROJECT_DBAPI]
    updated_project, _ = await db.patch_user_project_workbench(
        partial_workbench_data=partial_workbench_data,
        user_id=user_id,
        project_uuid=project_id,
    )
    updated_project = await add_project_states_for_user(
        user_id=user_id, project=updated_project, is_template=False, app=app
    )
    return updated_project


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
    partial_workbench_data = {
        node_id: {"progress": int(100.0 * float(progress) + 0.5)},
    }
    db = app[APP_PROJECT_DBAPI]
    updated_project, _ = await db.patch_user_project_workbench(
        partial_workbench_data=partial_workbench_data,
        user_id=user_id,
        project_uuid=project_id,
    )
    updated_project = await add_project_states_for_user(
        user_id=user_id, project=updated_project, is_template=False, app=app
    )
    return updated_project


async def update_project_node_outputs(
    app: web.Application,
    user_id: int,
    project_id: str,
    node_id: str,
    new_outputs: Optional[Dict],
    new_run_hash: Optional[str],
) -> Tuple[Dict, List[str]]:
    """
    Updates outputs of a given node in a project with 'data'
    """
    log.debug(
        "updating node %s outputs in project %s for user %s with %s: run_hash [%s]",
        node_id,
        project_id,
        user_id,
        pformat(new_outputs),
        new_run_hash,
    )
    new_outputs: Dict[str, Any] = new_outputs or {}

    partial_workbench_data = {
        node_id: {"outputs": new_outputs, "runHash": new_run_hash},
    }

    db = app[APP_PROJECT_DBAPI]
    updated_project, changed_entries = await db.patch_user_project_workbench(
        partial_workbench_data=partial_workbench_data,
        user_id=user_id,
        project_uuid=project_id,
    )
    log.debug(
        "patched project %s, following entries changed: %s",
        project_id,
        pformat(changed_entries),
    )
    updated_project = await add_project_states_for_user(
        user_id=user_id, project=updated_project, is_template=False, app=app
    )

    # changed entries come in the form of {node_uuid: {outputs: {changed_key1: value1, changed_key2: value2}}}
    # we do want only the key names
    changed_keys = changed_entries.get(node_id, {}).get("outputs", {}).keys()
    return updated_project, changed_keys


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


async def notify_project_node_update(
    app: web.Application, project: Dict, node_id: str
) -> None:
    rooms_to_notify = [
        f"{gid}" for gid, rights in project["accessRights"].items() if rights["read"]
    ]

    messages = {
        SOCKET_IO_NODE_UPDATED_EVENT: {
            "Node": node_id,
            "data": project["workbench"][node_id],
        }
    }

    for room in rooms_to_notify:
        await post_group_messages(app, room, messages)


async def post_trigger_connected_service_retrieve(**kwargs) -> None:
    await fire_and_forget_task(trigger_connected_service_retrieve(**kwargs))


async def trigger_connected_service_retrieve(
    app: web.Application, project: Dict, updated_node_uuid: str, changed_keys: List[str]
) -> None:
    workbench = project["workbench"]
    nodes_keys_to_update: Dict[str, List[str]] = defaultdict(list)
    # find the nodes that need to retrieve data
    for node_uuid, node in workbench.items():
        # check this node is dynamic
        if not _is_node_dynamic(node["key"]):
            continue

        # check whether this node has our updated node as linked inputs
        node_inputs = node.get("inputs", {})
        for port_key, port_value in node_inputs.items():
            # we look for node port links, not values
            if not isinstance(port_value, dict):
                continue

            input_node_uuid = port_value.get("nodeUuid")
            if input_node_uuid != updated_node_uuid:
                continue
            # so this node is linked to the updated one, now check if the port was changed?
            linked_input_port = port_value.get("output")
            if linked_input_port in changed_keys:
                nodes_keys_to_update[node_uuid].append(port_key)

    # call /retrieve on the nodes
    update_tasks = [
        request_retrieve_dyn_service(app, node, keys)
        for node, keys in nodes_keys_to_update.items()
    ]
    await logged_gather(*update_tasks)


# PROJECT STATE -------------------------------------------------------------------


async def _user_has_another_client_open(
    user_session_id_list: List[Tuple[int, str]], app: web.Application
) -> bool:
    # NOTE if there is an active socket in use, that means the client is active
    for user_id, client_session_id in user_session_id_list:
        with managed_resource(user_id, client_session_id, app) as rt:
            if await rt.get_socket_id() is not None:
                return True
    return False


async def _clean_user_disconnected_clients(
    user_session_id_list: List[Tuple[int, str]], app: web.Application
):
    for user_id, client_session_id in user_session_id_list:
        with managed_resource(user_id, client_session_id, app) as rt:
            if await rt.get_socket_id() is None:
                log.debug(
                    "removing disconnected project of user %s/%s",
                    user_id,
                    client_session_id,
                )
                await rt.remove(PROJECT_ID_KEY)


async def try_lock_project_for_user(
    user_id: int, project_uuid: str, client_session_id: str, app: web.Application
) -> bool:
    with managed_resource(user_id, client_session_id, app) as rt:
        try:
            async with await get_redis_lock_manager(app).lock(
                PROJECT_REDIS_LOCK_KEY.format(project_uuid),
                lock_timeout=None,
                lock_identifier=ProjectLocked(
                    value=True,
                    owner=Owner(user_id=user_id, **(await get_user_name(app, user_id))),
                    status=ProjectStatus.OPENING,
                ).json(),
            ):
                log.debug(
                    "project [%s] lock acquired, now checking if project is available",
                    project_uuid,
                )
                user_session_id_list: List[
                    Tuple[int, str]
                ] = await rt.find_users_of_resource(PROJECT_ID_KEY, project_uuid)

                if not user_session_id_list:
                    # no one has the project so we lock it
                    await rt.add(PROJECT_ID_KEY, project_uuid)
                    return True

                set_user_ids = {uid for uid, _ in user_session_id_list}
                if set_user_ids.issubset({user_id}):
                    # we are the only user
                    if not await _user_has_another_client_open(
                        user_session_id_list, app
                    ):
                        # steal the project
                        await rt.add(PROJECT_ID_KEY, project_uuid)
                        await _clean_user_disconnected_clients(
                            user_session_id_list, app
                        )
                        return True
                return False

        except aioredlock.LockError:
            # the project is currently locked
            return False


async def _get_project_lock_state(
    user_id: int,
    project_uuid: str,
    app: web.Application,
    client_session_id: Optional[str] = None,
) -> ProjectLocked:
    """returns the lock state of a project
    1. If a project is locked for any reason, first return the project as locked and STATUS defined by lock
    2. If a client_session_id is passed, then first check to see if the project is currently opened by this very user/tab combination, if yes returns the project as Locked and OPENED.
    3. If any other user that user_id is using the project (even disconnected before the TTL is finished) then the project is Locked and OPENED_OTHER_USER.
    4. If the same user is using the project with a valid socket id (meaning a tab is currently active) then the project is Locked and OPENED_OTHER_CLIENT.
    5. If the same user is using the project with NO socket id (meaning there is no current tab active) then the project is Unlocked and OPENED. which means the user can open it again.
    """
    log.debug("getting project [%s] lock state for user [%s]", project_uuid, user_id)
    if await get_redis_lock_manager(app).is_locked(
        PROJECT_REDIS_LOCK_KEY.format(project_uuid)
    ):
        log.debug("project [%s] is locked, getting metadata...", project_uuid)
        # so the project is currently locked. let's find out why
        # NOTE: we use the client connected to the lock database here
        project_locked: Optional[str] = await get_redis_lock_manager_client(app).get(
            PROJECT_REDIS_LOCK_KEY.format(project_uuid)
        )
        log.debug("project [%s] is locked, metadata: %s", project_uuid, project_locked)
        if project_locked:
            return ProjectLocked.parse_raw(project_locked)

    log.debug("checking whether project [%s] is locked and how", project_uuid)
    if client_session_id:
        # if a client session id is there, then let's check if the project is already opened by this user
        with managed_resource(user_id, client_session_id, app) as rt:
            opened_project_ids = await rt.find(PROJECT_ID_KEY)
            if project_uuid in opened_project_ids:
                log.debug(
                    "project [%s] is locked but opened by user %s",
                    project_uuid,
                    user_id,
                )
                return ProjectLocked(
                    value=True,
                    owner=Owner(user_id=user_id, **(await get_user_name(app, user_id))),
                    status=ProjectStatus.OPENED,
                )
    # let's now check if anyone has the project in use somehow
    with managed_resource(user_id, None, app) as rt:
        user_session_id_list: List[Tuple[int, str]] = await rt.find_users_of_resource(
            "project_id", project_uuid
        )
    set_user_ids = {x for x, _ in user_session_id_list}

    assert (
        len(set_user_ids) <= 1
    )  # nosec  # NOTE: A project can only be opened by one user in one tab at the moment

    if not set_user_ids:
        # no one has the project, so it is closed.
        log.debug("project [%s] is not locked", project_uuid)
        return ProjectLocked(value=False, status=ProjectStatus.CLOSED)

    log.debug(
        "project [%s] might be used by the following [%s]", project_uuid, set_user_ids
    )
    usernames: List[Dict[str, str]] = [
        await get_user_name(app, uid) for uid in set_user_ids
    ]
    # let's check if the project is opened by the same user, maybe already opened or closed in a orphaned session
    if set_user_ids.issubset({user_id}):
        if not await _user_has_another_client_open(user_session_id_list, app):
            # in this case the project is re-openable by the same user until it gets closed
            log.debug(
                "project [%s] is in use by the same user [%s] that is disconnected, so it is unlocked",
                project_uuid,
                set_user_ids,
            )
            return ProjectLocked(
                value=False,
                owner=Owner(user_id=list(set_user_ids)[0], **usernames[0]),
                status=ProjectStatus.OPENED,
            )
        # the project is opened in another tab or browser
        log.debug(
            "project [%s] is in use by another user [%s], so it is locked",
            project_uuid,
            set_user_ids,
        )
        return ProjectLocked(
            value=True,
            owner=Owner(user_id=list(set_user_ids)[0], **usernames[0]),
            status=ProjectStatus.OPENED_OTHER_CLIENT,
        )

    # The project is in use by another user
    owner = None
    owner = Owner(user_id=list(set_user_ids)[0], **usernames[0])
    return ProjectLocked(
        value=True,
        owner=owner,
        status=ProjectStatus.OPENED_OTHER_USER,
    )


async def add_project_states_for_user(
    user_id: int,
    project: Dict[str, Any],
    is_template: bool,
    app: web.Application,
    client_session_id: Optional[str] = None,
) -> Dict[str, Any]:

    # for templates: the project is never locked and never opened. also the running state is always unknown
    lock_state = ProjectLocked(value=False, status=ProjectStatus.CLOSED)
    running_state = RunningState.UNKNOWN
    if not is_template:
        lock_state, computation_task = await logged_gather(
            _get_project_lock_state(user_id, project["uuid"], app, client_session_id),
            get_computation_task(app, user_id, project["uuid"]),
        )

        if computation_task:
            # get the running state
            running_state = computation_task.state
            # get the nodes individual states
            for (
                node_id,
                node_state,
            ) in computation_task.pipeline_details.node_states.items():
                prj_node = project["workbench"].get(str(node_id))
                if prj_node is None:
                    continue
                node_state_dict = json.loads(
                    node_state.json(by_alias=True, exclude_unset=True)
                )
                prj_node.setdefault("state", {}).update(node_state_dict)

    project["state"] = ProjectState(
        locked=lock_state, state=ProjectRunningState(value=running_state)
    ).dict(by_alias=True, exclude_unset=True)
    return project
