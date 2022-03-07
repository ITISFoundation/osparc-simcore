""" Core module: project's nodes

"""
# TODO: separate plugin for sub-resources?

import logging
from collections import defaultdict
from pprint import pformat
from typing import Any, Dict, List, Optional, Set, Tuple
from uuid import uuid4

from aiohttp import web
from models_library.projects_state import RunningState
from servicelib.json_serialization import json_dumps
from servicelib.utils import fire_and_forget_task, logged_gather

from .. import director_v2_api
from ..socketio.events import (
    SOCKET_IO_NODE_UPDATED_EVENT,
    SOCKET_IO_PROJECT_UPDATED_EVENT,
    SocketMessageDict,
    send_group_messages,
    send_messages,
)
from ..storage_api import delete_data_folders_of_project_node
from ._core_states import add_project_states_for_user
from .projects_db import APP_PROJECT_DBAPI
from .projects_utils import extract_dns_without_default_port

log = logging.getLogger(__name__)


def is_node_dynamic(node_key: str) -> bool:
    return "/dynamic/" in node_key


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
    if is_node_dynamic(service_key):
        await director_v2_api.start_dynamic_service(
            request.app,
            project_id=project_uuid,
            user_id=user_id,
            service_key=service_key,
            service_version=service_version,
            service_uuid=node_uuid,
            request_dns=extract_dns_without_default_port(request.url),
            request_scheme=request.headers.get("X-Forwarded-Proto", request.url.scheme),
        )
    return node_uuid


async def get_project_node(
    request: web.Request, project_uuid: str, user_id: int, node_id: str
):
    log.debug(
        "getting node %s in project %s for user %s", node_id, project_uuid, user_id
    )

    list_of_interactive_services = await director_v2_api.get_dynamic_services(
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

    list_of_services = await director_v2_api.get_dynamic_services(
        request.app, project_id=project_uuid, user_id=user_id
    )
    # stop the service if it is running
    for service in list_of_services:
        if service["service_uuid"] == node_uuid:
            log.error("deleting service=%s", service)
            # no need to save the state of the node when deleting it
            await director_v2_api.stop_dynamic_service(
                request.app,
                node_uuid,
                save_state=False,
            )
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
    db = app[APP_PROJECT_DBAPI]
    return await db.get_all_node_ids_from_workbenches(project_uuid)


async def is_node_id_present_in_any_project_workbench(
    app: web.Application,
    node_id: str,
) -> bool:
    """If the node_id is presnet in one of the projects' workbenche returns True"""
    db = app[APP_PROJECT_DBAPI]
    return node_id in await db.get_all_node_ids_from_workbenches()


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
    app: web.Application, project: Dict, node_id: str
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
                "data": project["workbench"][node_id],
            },
        }
    ]

    for room in rooms_to_notify:
        await send_group_messages(app, room, messages)


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
        if not is_node_dynamic(node["key"]):
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
        director_v2_api.retrieve_dynamic_service_inputs(app, node, keys)
        for node, keys in nodes_keys_to_update.items()
    ]
    await logged_gather(*update_tasks)
