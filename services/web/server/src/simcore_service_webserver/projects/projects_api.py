""" Interface to other subsystems

    - Data validation
    - Operations on projects
        - are NOT handlers, therefore do not return web.Response
        - return data and successful HTTP responses (or raise them)
        - upon failure raise errors that can be also HTTP reponses
"""

import asyncio
import contextlib
import json
import logging
from collections import defaultdict
from contextlib import suppress
from pprint import pformat
from typing import Any, Dict, List, Optional, Set, Tuple
from uuid import UUID, uuid4

from aiohttp import web
from models_library.errors import ErrorDict
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from models_library.projects_state import (
    Owner,
    ProjectLocked,
    ProjectRunningState,
    ProjectState,
    ProjectStatus,
    RunningState,
)
from models_library.services_resources import ServiceResourcesDict
from models_library.users import UserID
from pydantic.types import PositiveInt
from servicelib.aiohttp.application_keys import (
    APP_FIRE_AND_FORGET_TASKS_KEY,
    APP_JSONSCHEMA_SPECS_KEY,
)
from servicelib.aiohttp.jsonschema_validation import validate_instance
from servicelib.json_serialization import json_dumps
from servicelib.observer import observe
from servicelib.utils import fire_and_forget_task, logged_gather

from .. import catalog_client, director_v2_api, storage_api
from ..resource_manager.websocket_manager import (
    PROJECT_ID_KEY,
    UserSessionID,
    managed_resource,
)
from ..socketio.events import (
    SOCKET_IO_NODE_UPDATED_EVENT,
    SOCKET_IO_PROJECT_UPDATED_EVENT,
    SocketMessageDict,
    send_group_messages,
    send_messages,
)
from ..users_api import UserRole, get_user_name, get_user_role
from ..users_exceptions import UserNotFoundError
from . import _delete
from .project_lock import UserNameDict, get_project_locked_state, lock_project
from .projects_db import APP_PROJECT_DBAPI, ProjectDBAPI
from .projects_exceptions import NodeNotFoundError, ProjectLockError
from .projects_utils import extract_dns_without_default_port

log = logging.getLogger(__name__)

PROJECT_REDIS_LOCK_KEY: str = "project:{}"


def _is_node_dynamic(node_key: str) -> bool:
    return "/dynamic/" in node_key


async def validate_project(app: web.Application, project: Dict):
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
) -> Dict:
    """Returns a VALID project accessible to user

    :raises ProjectNotFoundError: if no match found
    :return: schema-compliant project data
    :rtype: Dict
    """
    db: ProjectDBAPI = app[APP_PROJECT_DBAPI]
    assert db  # nosec

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


async def start_project_interactive_services(
    request: web.Request, project: Dict, user_id: PositiveInt
) -> None:
    # first get the services if they already exist
    log.debug(
        "getting running interactive services of project %s for user %s",
        f"{project['uuid']=}",
        f"{user_id=}",
    )
    running_services = await director_v2_api.get_services(
        request.app, user_id, project["uuid"]
    )
    log.debug(
        "Currently running services %s for user %s",
        f"{running_services=}",
        f"{user_id=}",
    )

    running_service_uuids = [x["service_uuid"] for x in running_services]
    # now start them if needed
    project_needed_services = {
        service_uuid: service
        for service_uuid, service in project["workbench"].items()
        if _is_node_dynamic(service["key"])
        and service_uuid not in running_service_uuids
    }
    log.debug("Starting services: %s", f"{project_needed_services=}")

    unique_project_needed_services = set(project_needed_services.keys())
    service_resources_result: List[ServiceResourcesDict] = await logged_gather(
        *[
            get_project_node_resources(request.app, project=project, node_id=node_uuid)
            for node_uuid in unique_project_needed_services
        ],
        reraise=True,
    )
    service_resources_search: Dict[str, ServiceResourcesDict] = dict(
        zip(unique_project_needed_services, service_resources_result)
    )

    start_service_tasks = [
        director_v2_api.start_service(
            request.app,
            user_id=user_id,
            project_id=project["uuid"],
            service_key=service["key"],
            service_version=service["version"],
            service_uuid=service_uuid,
            request_dns=extract_dns_without_default_port(request.url),
            request_scheme=request.headers.get("X-Forwarded-Proto", request.url.scheme),
            service_resources=service_resources_search[service_uuid],
        )
        for service_uuid, service in project_needed_services.items()
    ]
    results = await logged_gather(*start_service_tasks, reraise=True)
    log.debug("Services start result %s", results)
    for entry in results:
        if entry:
            # if the status is present in the results for the start_service
            # it means that the API call failed
            # also it is enforced that the status is different from 200 OK
            if entry.get("status", 200) != 200:
                log.error("Error while starting dynamic service %s", f"{entry=}")


async def submit_delete_project_task(
    app: web.Application, project_uuid: ProjectID, user_id: UserID
) -> asyncio.Task:
    """
    Marks a project as deleted and schedules a task to performe the entire removal workflow
    using user_id's permissions.

    If this task is already scheduled, it returns it otherwise it creates a new one.

    The returned task can be ignored to implement a fire&forget or
    followed up with add_done_callback.

    raises ProjectDeleteError
    raises ProjectInvalidRightsError
    raises ProjectNotFoundError
    """
    await _delete.mark_project_as_deleted(app, project_uuid, user_id)

    # Ensures ONE delete task per (project,user) pair
    task = get_delete_project_task(project_uuid, user_id)
    if not task:
        task = _delete.schedule_task(
            app, project_uuid, user_id, remove_project_dynamic_services, log
        )
    return task


def get_delete_project_task(
    project_uuid: ProjectID, user_id: UserID
) -> Optional[asyncio.Task]:
    if tasks := _delete.get_scheduled_tasks(project_uuid, user_id):
        assert len(tasks) == 1, f"{tasks=}"  # nosec
        task = tasks[0]
        return task
    return None


@observe(event="SIGNAL_USER_DISCONNECTED")
async def user_disconnected(
    user_id: int, client_session_id: str, app: web.Application
) -> None:
    # check if there is a project resource
    with managed_resource(user_id, client_session_id, app) as rt:
        list_projects: List[str] = await rt.find(PROJECT_ID_KEY)

    await logged_gather(
        *[
            retrieve_and_notify_project_locked_state(
                user_id, prj, app, notify_only_prj_user=True
            )
            for prj in list_projects
        ]
    )


async def retrieve_and_notify_project_locked_state(
    user_id: int,
    project_uuid: str,
    app: web.Application,
    notify_only_prj_user: bool = False,
):
    project = await get_project_for_user(app, project_uuid, user_id, include_state=True)
    await notify_project_state_update(
        app, project, notify_only_user=user_id if notify_only_prj_user else None
    )


@contextlib.asynccontextmanager
async def lock_with_notification(
    app: web.Application,
    project_uuid: str,
    status: ProjectStatus,
    user_id: int,
    user_name: UserNameDict,
    notify_users: bool = True,
):
    try:
        async with lock_project(
            app,
            project_uuid,
            status,
            user_id,
            user_name,
        ):
            log.debug(
                "Project [%s] lock acquired",
                f"{project_uuid=}",
            )
            if notify_users:
                await retrieve_and_notify_project_locked_state(
                    user_id, project_uuid, app
                )
            yield
        log.debug(
            "Project [%s] lock released",
            f"{project_uuid=}",
        )
    except ProjectLockError:
        # someone else has already the lock?
        prj_states: ProjectState = await get_project_states_for_user(
            user_id, project_uuid, app
        )
        log.error(
            "Project [%s] already locked in state '%s'. Please check with support.",
            f"{project_uuid=}",
            f"{prj_states.locked.status=}",
        )
        raise
    finally:
        if notify_users:
            await retrieve_and_notify_project_locked_state(user_id, project_uuid, app)


async def remove_project_dynamic_services(
    user_id: int,
    project_uuid: str,
    app: web.Application,
    notify_users: bool = True,
    user_name: Optional[UserNameDict] = None,
) -> None:
    """

    :raises UserNotFoundError:
    """

    # NOTE: during the closing process, which might take awhile,
    # the project is locked so no one opens it at the same time
    log.debug(
        "removing project interactive services for project [%s] and user [%s]",
        project_uuid,
        user_id,
    )
    try:
        user_name_data: UserNameDict = user_name or await get_user_name(app, user_id)

        # TODO: logic around save_state is not ideal, but it remains with the same logic
        # as before until it is properly refactored
        user_role: Optional[UserRole] = None
        try:
            user_role = await get_user_role(app, user_id)
        except UserNotFoundError:
            user_role = None

        save_state: bool = True
        if user_role is None or user_role <= UserRole.GUEST:
            save_state = False
        # -------------------

        async with lock_with_notification(
            app,
            project_uuid,
            ProjectStatus.CLOSING,
            user_id,
            user_name_data,
            notify_users=notify_users,
        ):
            # save the state if the user is not a guest. if we do not know we save in any case.
            with suppress(director_v2_api.DirectorServiceError):
                # here director exceptions are suppressed. in case the service is not found to preserve old behavior
                await director_v2_api.stop_services(
                    app=app,
                    user_id=user_id,
                    project_id=project_uuid,
                    save_state=save_state,
                )
    except ProjectLockError:
        pass


## PROJECT NODES -----------------------------------------------------


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
        service_resources: ServiceResourcesDict = await get_project_node_resources(
            request.app,
            project={
                "workbench": {
                    f"{node_uuid}": {"key": service_key, "version": service_version}
                }
            },
            node_id=UUID(node_uuid),
        )
        await director_v2_api.start_service(
            request.app,
            project_id=project_uuid,
            user_id=user_id,
            service_key=service_key,
            service_version=service_version,
            service_uuid=node_uuid,
            request_dns=extract_dns_without_default_port(request.url),
            request_scheme=request.headers.get("X-Forwarded-Proto", request.url.scheme),
            service_resources=service_resources,
        )
    return node_uuid


async def delete_project_node(
    request: web.Request, project_uuid: str, user_id: int, node_uuid: str
) -> None:
    log.debug(
        "deleting node %s in project %s for user %s", node_uuid, project_uuid, user_id
    )

    list_of_services = await director_v2_api.get_services(
        request.app, project_id=project_uuid, user_id=user_id
    )
    # stop the service if it is running
    for service in list_of_services:
        if service["service_uuid"] == node_uuid:
            log.error("deleting service=%s", service)
            # no need to save the state of the node when deleting it
            await director_v2_api.stop_service(
                request.app,
                node_uuid,
                save_state=False,
            )
            break
    # remove its data if any
    await storage_api.delete_data_folders_of_project_node(
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
    partial_workbench_data: Dict[str, Any] = {
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
        json_dumps(new_outputs),
        new_run_hash,
    )
    new_outputs = new_outputs or {}

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
    db: ProjectDBAPI = app[APP_PROJECT_DBAPI]
    return await db.get_node_ids_from_project(project_uuid)


async def is_node_id_present_in_any_project_workbench(
    app: web.Application,
    node_id: str,
) -> bool:
    """If the node_id is presnet in one of the projects' workbenche returns True"""
    db: ProjectDBAPI = app[APP_PROJECT_DBAPI]
    return await db.node_id_exists(node_id)


async def notify_project_state_update(
    app: web.Application,
    project: Dict,
    notify_only_user: Optional[int] = None,
) -> None:
    messages: List[SocketMessageDict] = [
        {
            "event_type": SOCKET_IO_PROJECT_UPDATED_EVENT,
            "data": {
                "project_uuid": project["uuid"],
                "data": project["state"],
            },
        }
    ]

    if notify_only_user:
        await send_messages(app, user_id=str(notify_only_user), messages=messages)
    else:
        rooms_to_notify = [
            f"{gid}"
            for gid, rights in project["accessRights"].items()
            if rights["read"]
        ]
        for room in rooms_to_notify:
            await send_group_messages(app, room, messages)


async def notify_project_node_update(
    app: web.Application,
    project: Dict,
    node_id: str,
    errors: Optional[List[ErrorDict]],
) -> None:
    rooms_to_notify = [
        f"{gid}" for gid, rights in project["accessRights"].items() if rights["read"]
    ]

    messages: List[SocketMessageDict] = [
        {
            "event_type": SOCKET_IO_NODE_UPDATED_EVENT,
            "data": {
                "project_id": project["uuid"],
                "node_id": node_id,
                # as GET projects/{project_id}/nodes/{node_id}
                "data": project["workbench"][node_id],
                # as GET projects/{project_id}/nodes/{node_id}/errors
                "errors": errors,
            },
        }
    ]

    for room in rooms_to_notify:
        await send_group_messages(app, room, messages)


async def post_trigger_connected_service_retrieve(
    app: web.Application, **kwargs
) -> None:
    await fire_and_forget_task(
        trigger_connected_service_retrieve(app, **kwargs),
        task_suffix_name="trigger_connected_service_retrieve",
        fire_and_forget_tasks_collection=app[APP_FIRE_AND_FORGET_TASKS_KEY],
    )


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
        director_v2_api.request_retrieve_dyn_service(app, node, keys)
        for node, keys in nodes_keys_to_update.items()
    ]
    await logged_gather(*update_tasks)


# PROJECT STATE -------------------------------------------------------------------


async def _user_has_another_client_open(
    user_session_id_list: List[UserSessionID], app: web.Application
) -> bool:
    # NOTE if there is an active socket in use, that means the client is active
    for user_session in user_session_id_list:
        with managed_resource(
            user_session.user_id, user_session.client_session_id, app
        ) as rt:
            if await rt.get_socket_id() is not None:
                return True
    return False


async def _clean_user_disconnected_clients(
    user_session_id_list: List[UserSessionID], app: web.Application
):
    for user_session in user_session_id_list:
        with managed_resource(
            user_session.user_id, user_session.client_session_id, app
        ) as rt:
            if await rt.get_socket_id() is None:
                log.debug(
                    "removing disconnected project of user %s/%s",
                    user_session.user_id,
                    user_session.client_session_id,
                )
                await rt.remove(PROJECT_ID_KEY)


async def try_open_project_for_user(
    user_id: int, project_uuid: str, client_session_id: str, app: web.Application
) -> bool:
    try:
        async with lock_with_notification(
            app,
            project_uuid,
            ProjectStatus.OPENING,
            user_id,
            await get_user_name(app, user_id),
            notify_users=False,
        ):

            with managed_resource(user_id, client_session_id, app) as rt:
                user_session_id_list: List[
                    UserSessionID
                ] = await rt.find_users_of_resource(PROJECT_ID_KEY, project_uuid)

                if not user_session_id_list:
                    # no one has the project so we lock it
                    await rt.add(PROJECT_ID_KEY, project_uuid)
                    return True

                set_user_ids = {
                    user_session.user_id for user_session in user_session_id_list
                }
                if set_user_ids.issubset({user_id}):
                    # we are the only user, remove this session from the list
                    if not await _user_has_another_client_open(
                        [
                            uid
                            for uid in user_session_id_list
                            if uid != UserSessionID(user_id, client_session_id)
                        ],
                        app,
                    ):
                        # steal the project
                        await rt.add(PROJECT_ID_KEY, project_uuid)
                        await _clean_user_disconnected_clients(
                            user_session_id_list, app
                        )
                        return True
            return False

    except ProjectLockError:
        # the project is currently locked
        return False


async def try_close_project_for_user(
    user_id: int,
    project_uuid: str,
    client_session_id: str,
    app: web.Application,
):
    with managed_resource(user_id, client_session_id, app) as rt:
        user_to_session_ids: List[UserSessionID] = await rt.find_users_of_resource(
            PROJECT_ID_KEY, project_uuid
        )
        # first check we have it opened now
        if UserSessionID(user_id, client_session_id) not in user_to_session_ids:
            # nothing to do the project is already closed
            log.warning(
                "project [%s] is already closed for user [%s].",
                project_uuid,
                user_id,
            )
            return
        # remove the project from our list of opened ones
        log.debug(
            "removing project [%s] from user [%s] resources", project_uuid, user_id
        )
        await rt.remove(PROJECT_ID_KEY)
    # check it is not opened by someone else
    user_to_session_ids.remove(UserSessionID(user_id, client_session_id))
    log.debug("remaining user_to_session_ids: %s", user_to_session_ids)
    if not user_to_session_ids:
        # NOTE: depending on the garbage collector speed, it might already be removing it
        fire_and_forget_task(
            remove_project_dynamic_services(user_id, project_uuid, app),
            task_suffix_name=f"remove_project_dynamic_services_{user_id=}_{project_uuid=}",
            fire_and_forget_tasks_collection=app[APP_FIRE_AND_FORGET_TASKS_KEY],
        )
    else:
        log.warning(
            "project [%s] is used by other users: [%s]. This should not be possible",
            project_uuid,
            {user_session.user_id for user_session in user_to_session_ids},
        )


async def _get_project_lock_state(
    user_id: int,
    project_uuid: str,
    app: web.Application,
) -> ProjectLocked:
    """returns the lock state of a project
    1. If a project is locked for any reason, first return the project as locked and STATUS defined by lock
    2. If a client_session_id is passed, then first check to see if the project is currently opened by this very user/tab combination, if yes returns the project as Locked and OPENED.
    3. If any other user than user_id is using the project (even disconnected before the TTL is finished) then the project is Locked and OPENED.
    4. If the same user is using the project with a valid socket id (meaning a tab is currently active) then the project is Locked and OPENED.
    5. If the same user is using the project with NO socket id (meaning there is no current tab active) then the project is Unlocked and OPENED. which means the user can open it again.
    """
    log.debug(
        "getting project [%s] lock state for user [%s]...",
        f"{project_uuid=}",
        f"{user_id=}",
    )
    prj_locked_state: Optional[ProjectLocked] = await get_project_locked_state(
        app, project_uuid
    )
    if prj_locked_state:
        log.debug(
            "project [%s] is locked: %s", f"{project_uuid=}", f"{prj_locked_state=}"
        )
        return prj_locked_state

    # let's now check if anyone has the project in use somehow
    with managed_resource(user_id, None, app) as rt:
        user_session_id_list: List[UserSessionID] = await rt.find_users_of_resource(
            PROJECT_ID_KEY, project_uuid
        )
    set_user_ids = {user_session.user_id for user_session in user_session_id_list}

    assert (  # nosec
        len(set_user_ids) <= 1
    )  # nosec  # NOTE: A project can only be opened by one user in one tab at the moment

    if not set_user_ids:
        # no one has the project, so it is unlocked and closed.
        log.debug("project [%s] is not in use", f"{project_uuid=}")
        return ProjectLocked(value=False, status=ProjectStatus.CLOSED)

    log.debug(
        "project [%s] might be used by the following users: [%s]",
        f"{project_uuid=}",
        f"{set_user_ids=}",
    )
    usernames: List[UserNameDict] = [
        await get_user_name(app, uid) for uid in set_user_ids
    ]
    # let's check if the project is opened by the same user, maybe already opened or closed in a orphaned session
    if set_user_ids.issubset({user_id}):
        if not await _user_has_another_client_open(user_session_id_list, app):
            # in this case the project is re-openable by the same user until it gets closed
            log.debug(
                "project [%s] is in use by the same user [%s] that is currently disconnected, so it is unlocked for this specific user and opened",
                f"{project_uuid=}",
                f"{set_user_ids=}",
            )
            return ProjectLocked(
                value=False,
                owner=Owner(user_id=list(set_user_ids)[0], **usernames[0]),
                status=ProjectStatus.OPENED,
            )
    # the project is opened in another tab or browser, or by another user, both case resolves to the project being locked, and opened
    log.debug(
        "project [%s] is in use by another user [%s], so it is locked",
        f"{project_uuid=}",
        f"{set_user_ids=}",
    )
    return ProjectLocked(
        value=True,
        owner=Owner(user_id=list(set_user_ids)[0], **usernames[0]),
        status=ProjectStatus.OPENED,
    )


async def get_project_states_for_user(
    user_id: int, project_uuid: str, app: web.Application
) -> ProjectState:
    # for templates: the project is never locked and never opened. also the running state is always unknown
    lock_state = ProjectLocked(value=False, status=ProjectStatus.CLOSED)
    running_state = RunningState.UNKNOWN
    lock_state, computation_task = await logged_gather(
        _get_project_lock_state(user_id, project_uuid, app),
        director_v2_api.get_computation_task(app, user_id, UUID(project_uuid)),
    )
    if computation_task:
        # get the running state
        running_state = computation_task.state

    return ProjectState(
        locked=lock_state, state=ProjectRunningState(value=running_state)
    )


async def add_project_states_for_user(
    user_id: int,
    project: Dict[str, Any],
    is_template: bool,
    app: web.Application,
) -> Dict[str, Any]:
    log.debug(
        "adding project states for %s with project %s",
        f"{user_id=}",
        f"{project['uuid']=}",
    )
    # for templates: the project is never locked and never opened. also the running state is always unknown
    lock_state = ProjectLocked(value=False, status=ProjectStatus.CLOSED)
    running_state = RunningState.UNKNOWN

    if not is_template:
        lock_state = await _get_project_lock_state(user_id, project["uuid"], app)

        if computation_task := await director_v2_api.get_computation_task(
            app, user_id, project["uuid"]
        ):
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


async def get_project_node_resources(
    app: web.Application, project: dict[str, Any], node_id: NodeID
) -> ServiceResourcesDict:
    if project_node := project.get("workbench", {}).get(f"{node_id}"):
        return await catalog_client.get_service_resources(
            app, project_node["key"], project_node["version"]
        )
    raise NodeNotFoundError(project["uuid"], f"{node_id}")


async def set_project_node_resources(
    app: web.Application, project: dict[str, Any], node_id: NodeID
):
    raise NotImplementedError("cannot change resources for now")
