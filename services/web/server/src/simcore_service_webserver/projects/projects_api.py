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
from datetime import datetime
from pprint import pformat
from typing import Any, Optional
from uuid import UUID, uuid4

from aiohttp import web
from models_library.errors import ErrorDict
from models_library.projects import ProjectID
from models_library.projects_nodes import Node
from models_library.projects_nodes_io import NodeID, NodeIDStr
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
from models_library.utils.fastapi_encoders import jsonable_encoder
from pydantic import parse_obj_as
from servicelib.aiohttp.application_keys import (
    APP_FIRE_AND_FORGET_TASKS_KEY,
    APP_JSONSCHEMA_SPECS_KEY,
)
from servicelib.aiohttp.jsonschema_validation import validate_instance
from servicelib.json_serialization import json_dumps
from servicelib.logging_utils import log_context
from servicelib.utils import fire_and_forget_task, logged_gather
from simcore_postgres_database.webserver_models import ProjectType

from .. import catalog_client, director_v2_api, storage_api
from ..application_settings import get_settings
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
from .project_lock import (
    UserNameDict,
    get_project_locked_state,
    is_project_locked,
    lock_project,
)
from .projects_db import APP_PROJECT_DBAPI, ProjectDBAPI
from .projects_exceptions import (
    NodeNotFoundError,
    ProjectLockError,
    ProjectStartsTooManyDynamicNodes,
    ProjectTooManyProjectOpened,
)
from .projects_utils import extract_dns_without_default_port

log = logging.getLogger(__name__)

PROJECT_REDIS_LOCK_KEY: str = "project:{}"


def _is_node_dynamic(node_key: str) -> bool:
    return "/dynamic/" in node_key


async def validate_project(app: web.Application, project: dict):
    project_schema = app[APP_JSONSCHEMA_SPECS_KEY]["projects"]
    await asyncio.get_event_loop().run_in_executor(
        None, validate_instance, project, project_schema
    )


#
# GET project -----------------------------------------------------
#


async def get_project_for_user(
    app: web.Application,
    project_uuid: str,
    user_id: UserID,
    *,
    include_state: Optional[bool] = False,
    check_permissions: str = "read",
) -> dict:
    """Returns a VALID project accessible to user

    :raises ProjectNotFoundError: if no match found
    :return: schema-compliant project data
    :rtype: Dict
    """
    db = ProjectDBAPI.get_from_app_context(app)

    project, project_type = await db.get_project(
        user_id,
        project_uuid,
        check_permissions=check_permissions,
    )

    # adds state if it is not a template
    if include_state:
        project = await add_project_states_for_user(
            user_id, project, project_type is ProjectType.TEMPLATE, app
        )

    await validate_project(app, project)
    return project


async def get_project_type(
    app: web.Application, project_uuid: ProjectID
) -> ProjectType:
    db: ProjectDBAPI = app[APP_PROJECT_DBAPI]
    assert db  # nosec
    return await db.get_project_type(project_uuid)


#
# DELETE project -----------------------------------------------------
#


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


#
# PROJECT NODES -----------------------------------------------------
#


async def _start_dynamic_service(
    request: web.Request,
    *,
    service_key: str,
    service_version: str,
    product_name: str,
    user_id: UserID,
    project_uuid: ProjectID,
    node_uuid: NodeID,
):
    if not _is_node_dynamic(service_key):
        return
    project_running_nodes = await director_v2_api.list_dynamic_services(
        request.app, user_id, f"{project_uuid}"
    )

    project_settings = get_settings(request.app).WEBSERVER_PROJECTS
    assert project_settings  # nosec
    if project_settings.PROJECTS_MAX_NUM_RUNNING_DYNAMIC_NODES > 0 and (
        len(project_running_nodes)
        >= project_settings.PROJECTS_MAX_NUM_RUNNING_DYNAMIC_NODES
    ):
        raise ProjectStartsTooManyDynamicNodes(
            user_id=user_id, project_uuid=project_uuid
        )

    # this is a dynamic node, let's gather its resources and start it
    service_resources: ServiceResourcesDict = await get_project_node_resources(
        request.app,
        user_id=user_id,
        project={
            "workbench": {
                f"{node_uuid}": {"key": service_key, "version": service_version}
            }
        },
        node_id=node_uuid,
    )

    await director_v2_api.run_dynamic_service(
        app=request.app,
        product_name=product_name,
        project_id=f"{project_uuid}",
        user_id=user_id,
        service_key=service_key,
        service_version=service_version,
        service_uuid=f"{node_uuid}",
        request_dns=extract_dns_without_default_port(request.url),
        request_scheme=request.headers.get("X-Forwarded-Proto", request.url.scheme),
        request_user_agent=request.headers.get("User-Agent", ""),
        service_resources=service_resources,
    )


async def add_project_node(
    request: web.Request,
    project: dict[str, Any],
    user_id: UserID,
    product_name: str,
    service_key: str,
    service_version: str,
    service_id: Optional[str],
) -> str:
    log.debug(
        "starting node %s:%s in project %s for user %s",
        service_key,
        service_version,
        project["uuid"],
        user_id,
    )
    node_uuid = service_id if service_id else f"{uuid4()}"

    # ensure the project is up-to-date in the database prior to start any potential service
    partial_workbench_data: dict[str, Any] = {
        node_uuid: jsonable_encoder(
            Node.parse_obj(
                {
                    "key": service_key,
                    "version": service_version,
                    "label": service_key.split("/")[-1],
                }
            ),
            exclude_unset=True,
        ),
    }
    db: ProjectDBAPI = request.app[APP_PROJECT_DBAPI]
    assert db  # nosec
    await db.update_project_workbench(
        partial_workbench_data, user_id, project["uuid"], product_name
    )
    # also ensure the project is updated by director-v2 since services
    # are due to access comp_tasks at some point see [https://github.com/ITISFoundation/osparc-simcore/issues/3216]
    await director_v2_api.create_or_update_pipeline(
        request.app, user_id, project["uuid"]
    )

    if _is_node_dynamic(service_key):
        with suppress(ProjectStartsTooManyDynamicNodes):
            # NOTE: we do not start the service if there are already too many
            await _start_dynamic_service(
                request,
                service_key=service_key,
                service_version=service_version,
                product_name=product_name,
                user_id=user_id,
                project_uuid=ProjectID(project["uuid"]),
                node_uuid=NodeID(node_uuid),
            )

    return node_uuid


async def start_project_node(
    request: web.Request,
    product_name: str,
    user_id: UserID,
    project_id: ProjectID,
    node_id: NodeID,
):
    project = await get_project_for_user(request.app, f"{project_id}", user_id)
    workbench = project.get("workbench", {})
    if not workbench.get(f"{node_id}"):
        raise NodeNotFoundError(project_uuid=f"{project_id}", node_uuid=f"{node_id}")
    node_details = Node.construct(**workbench[f"{node_id}"])

    await _start_dynamic_service(
        request,
        service_key=node_details.key,
        service_version=node_details.version,
        product_name=product_name,
        user_id=user_id,
        project_uuid=project_id,
        node_uuid=node_id,
    )


async def delete_project_node(
    request: web.Request, project_uuid: ProjectID, user_id: UserID, node_uuid: str
) -> None:
    log.debug(
        "deleting node %s in project %s for user %s", node_uuid, project_uuid, user_id
    )

    list_running_dynamic_services = await director_v2_api.list_dynamic_services(
        request.app, project_id=f"{project_uuid}", user_id=user_id
    )
    if any(s["service_uuid"] == node_uuid for s in list_running_dynamic_services):
        # no need to save the state of the node when deleting it
        await director_v2_api.stop_dynamic_service(
            request.app,
            node_uuid,
            save_state=False,
        )

    # remove the node's data if any
    await storage_api.delete_data_folders_of_project_node(
        request.app, f"{project_uuid}", node_uuid, user_id
    )

    # remove the node from the db
    partial_workbench_data: dict[str, Any] = {
        node_uuid: None,
    }
    db: ProjectDBAPI = request.app[APP_PROJECT_DBAPI]
    assert db  # nosec
    await db.update_project_workbench(
        partial_workbench_data, user_id, f"{project_uuid}"
    )
    # also ensure the project is updated by director-v2 since services
    await director_v2_api.create_or_update_pipeline(request.app, user_id, project_uuid)


async def update_project_linked_product(
    app: web.Application, project_id: ProjectID, product_name: str
) -> None:
    with log_context(log, level=logging.DEBUG, msg="updating project linked product"):
        db: ProjectDBAPI = app[APP_PROJECT_DBAPI]
        await db.upsert_project_linked_product(project_id, product_name)


async def update_project_node_state(
    app: web.Application, user_id: int, project_id: str, node_id: str, new_state: str
) -> dict:
    log.debug(
        "updating node %s current state in project %s for user %s",
        node_id,
        project_id,
        user_id,
    )
    partial_workbench_data: dict[str, Any] = {
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

    db: ProjectDBAPI = app[APP_PROJECT_DBAPI]
    updated_project, _ = await db.update_project_workbench(
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
) -> Optional[dict]:
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
    db: ProjectDBAPI = app[APP_PROJECT_DBAPI]
    updated_project, _ = await db.update_project_workbench(
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
    new_outputs: Optional[dict],
    new_run_hash: Optional[str],
) -> tuple[dict, list[str]]:
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

    db: ProjectDBAPI = app[APP_PROJECT_DBAPI]
    updated_project, changed_entries = await db.update_project_workbench(
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
) -> set[str]:
    """Returns a set with all the node_ids from a project's workbench"""
    db: ProjectDBAPI = app[APP_PROJECT_DBAPI]
    return await db.list_node_ids_in_project(project_uuid)


async def is_node_id_present_in_any_project_workbench(
    app: web.Application,
    node_id: str,
) -> bool:
    """If the node_id is presnet in one of the projects' workbenche returns True"""
    db: ProjectDBAPI = app[APP_PROJECT_DBAPI]
    return await db.node_id_exists(node_id)


async def _trigger_connected_service_retrieve(
    app: web.Application, project: dict, updated_node_uuid: str, changed_keys: list[str]
) -> None:
    project_id = project["uuid"]
    if await is_project_locked(app, project_id):
        # NOTE: we log warn since this function is fire&forget and raise an exception would not be anybody to handle it
        log.warning(
            "Skipping service retrieval because project with %s is currently locked."
            "Operation triggered by %s",
            f"{project_id=}",
            f"{changed_keys=}",
        )
        return

    workbench = project["workbench"]
    nodes_keys_to_update: dict[str, list[str]] = defaultdict(list)

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


async def post_trigger_connected_service_retrieve(
    app: web.Application, **kwargs
) -> None:
    await fire_and_forget_task(
        _trigger_connected_service_retrieve(app, **kwargs),
        task_suffix_name="trigger_connected_service_retrieve",
        fire_and_forget_tasks_collection=app[APP_FIRE_AND_FORGET_TASKS_KEY],
    )


#
# OPEN PROJECT -------------------------------------------------------------------
#


async def _user_has_another_client_open(
    user_session_id_list: list[UserSessionID], app: web.Application
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
    user_session_id_list: list[UserSessionID], app: web.Application
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
    user_id: UserID,
    project_uuid: str,
    client_session_id: str,
    app: web.Application,
    max_number_of_studies_per_user: Optional[int],
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
                # NOTE: if max_number_of_studies_per_user is set, the same
                # project shall still be openable if the tab was closed
                if max_number_of_studies_per_user is not None and (
                    len(
                        {
                            uuid
                            for uuid in await rt.find_all_resources_of_user(
                                PROJECT_ID_KEY
                            )
                            if uuid != project_uuid
                        }
                    )
                    >= max_number_of_studies_per_user
                ):
                    raise ProjectTooManyProjectOpened(
                        max_num_projects=max_number_of_studies_per_user
                    )

                user_session_id_list: list[
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


#
# CLOSE PROJECT -------------------------------------------------------------------
#


async def try_close_project_for_user(
    user_id: int,
    project_uuid: str,
    client_session_id: str,
    app: web.Application,
):
    with managed_resource(user_id, client_session_id, app) as rt:
        user_to_session_ids: list[UserSessionID] = await rt.find_users_of_resource(
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


#
#  PROJECT STATE -------------------------------------------------------------------
#


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
        user_session_id_list: list[UserSessionID] = await rt.find_users_of_resource(
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
    usernames: list[UserNameDict] = [
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
    project: dict[str, Any],
    is_template: bool,
    app: web.Application,
) -> dict[str, Any]:
    log.debug(
        "adding project states for %s with project %s",
        f"{user_id=}",
        f"{project['uuid']=}",
    )
    # for templates: the project is never locked and never opened. also the running state is always unknown
    lock_state = await _get_project_lock_state(user_id, project["uuid"], app)
    running_state = RunningState.UNKNOWN

    if not is_template:
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


#
# SERVICE DEPRECATION ----------------------------
#
async def is_service_deprecated(
    app: web.Application,
    user_id: UserID,
    service_key: str,
    service_version: str,
    product_name: str,
) -> bool:
    service = await catalog_client.get_service(
        app, user_id, service_key, service_version, product_name
    )
    if deprecation_date := service.get("deprecated"):
        deprecation_date = parse_obj_as(datetime, deprecation_date)
        return datetime.utcnow() > deprecation_date
    return False


async def is_project_node_deprecated(
    app: web.Application,
    user_id: UserID,
    project: dict[str, Any],
    node_id: NodeID,
    product_name: str,
) -> bool:
    if project_node := project.get("workbench", {}).get(f"{node_id}"):
        return await is_service_deprecated(
            app, user_id, project_node["key"], project_node["version"], product_name
        )
    raise NodeNotFoundError(project["uuid"], f"{node_id}")


#
# SERVICE RESOURCES -----------------------------------
#


async def get_project_node_resources(
    app: web.Application, user_id: UserID, project: dict[str, Any], node_id: NodeID
) -> ServiceResourcesDict:
    if project_node := project.get("workbench", {}).get(f"{node_id}"):
        default_service_resources = await catalog_client.get_service_resources(
            app, user_id, project_node["key"], project_node["version"]
        )
        return default_service_resources
    raise NodeNotFoundError(project["uuid"], f"{node_id}")


async def set_project_node_resources(
    app: web.Application, project: dict[str, Any], node_id: NodeID
):
    raise NotImplementedError("cannot change resources for now")


#
# PROJECT DYNAMIC SERVICES -----------------------------------------------------
#


async def run_project_dynamic_services(
    request: web.Request, project: dict, user_id: UserID, product_name: str
) -> None:
    # first get the services if they already exist
    project_settings = get_settings(request.app).WEBSERVER_PROJECTS
    assert project_settings  # nosec
    running_service_uuids: list[NodeIDStr] = [
        d["service_uuid"]
        for d in await director_v2_api.list_dynamic_services(
            request.app, user_id, project["uuid"]
        )
    ]
    # find what needs to be started
    project_missing_services: dict[NodeIDStr, dict[str, Any]] = {
        service_uuid: service
        for service_uuid, service in project["workbench"].items()
        if _is_node_dynamic(service["key"])
        and service_uuid not in running_service_uuids
    }
    if project_settings.PROJECTS_MAX_NUM_RUNNING_DYNAMIC_NODES > 0 and (
        (len(project_missing_services) + len(running_service_uuids))
        > project_settings.PROJECTS_MAX_NUM_RUNNING_DYNAMIC_NODES
    ):
        # we cannot start so many services so we are done
        raise ProjectStartsTooManyDynamicNodes(
            user_id=user_id, project_uuid=ProjectID(project["uuid"])
        )

    deprecated_services: list[bool] = await logged_gather(
        *(
            is_service_deprecated(
                request.app,
                user_id,
                project_missing_services[service_uuid]["key"],
                project_missing_services[service_uuid]["version"],
                product_name,
            )
            for service_uuid in project_missing_services
        ),
        reraise=True,
    )

    await logged_gather(
        *(
            _start_dynamic_service(
                request,
                service_key=project_missing_services[service_uuid]["key"],
                service_version=project_missing_services[service_uuid]["version"],
                product_name=product_name,
                user_id=user_id,
                project_uuid=project["uuid"],
                node_uuid=NodeID(service_uuid),
            )
            for service_uuid, is_deprecated in zip(
                project_missing_services, deprecated_services
            )
            if not is_deprecated
        ),
        reraise=True,
    )


async def remove_project_dynamic_services(
    user_id: int,
    project_uuid: str,
    app: web.Application,
    notify_users: bool = True,
    user_name: Optional[UserNameDict] = None,
) -> None:
    """

    :raises UserNotFoundError:
    :raises ProjectLockError
    """

    # NOTE: during the closing process, which might take awhile,
    # the project is locked so no one opens it at the same time
    log.debug(
        "removing project interactive services for project [%s] and user [%s]",
        project_uuid,
        user_id,
    )

    user_name_data: UserNameDict = user_name or await get_user_name(app, user_id)

    user_role: Optional[UserRole] = None
    try:
        user_role = await get_user_role(app, user_id)
    except UserNotFoundError:
        user_role = None

    save_state = await ProjectDBAPI.get_from_app_context(app).has_permission(
        user_id=user_id, project_uuid=project_uuid, permission="write"
    )
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
            await director_v2_api.stop_dynamic_services_in_project(
                app=app,
                user_id=user_id,
                project_id=project_uuid,
                save_state=save_state,
            )


#
# NOTIFICATIONS & LOCKS -----------------------------------------------------
#


async def notify_project_state_update(
    app: web.Application,
    project: dict,
    notify_only_user: Optional[int] = None,
) -> None:
    messages: list[SocketMessageDict] = [
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
    project: dict,
    node_id: str,
    errors: Optional[list[ErrorDict]],
) -> None:
    rooms_to_notify = [
        f"{gid}" for gid, rights in project["accessRights"].items() if rights["read"]
    ]

    messages: list[SocketMessageDict] = [
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
