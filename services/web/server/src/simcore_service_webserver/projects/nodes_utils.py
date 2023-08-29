import logging
from collections import deque
from typing import Any, Coroutine

from aiohttp import web
from models_library.errors import ErrorDict
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from models_library.users import UserID
from servicelib.aiohttp.application_keys import APP_FIRE_AND_FORGET_TASKS_KEY
from servicelib.logging_utils import log_decorator
from servicelib.utils import fire_and_forget_task, logged_gather

from . import projects_api
from .utils import get_frontend_node_outputs_changes

log = logging.getLogger(__name__)


async def project_get_depending_nodes(
    project: dict[str, Any], node_uuid: NodeID
) -> set[NodeID]:
    depending_node_uuids = set()
    for dep_node_uuid, dep_node_data in project.get("workbench", {}).items():
        for dep_node_inputs_key_data in dep_node_data.get("inputs", {}).values():
            if (
                isinstance(dep_node_inputs_key_data, dict)
                and dep_node_inputs_key_data.get("nodeUuid") == f"{node_uuid}"
            ):
                depending_node_uuids.add(NodeID(dep_node_uuid))

    return depending_node_uuids


@log_decorator(logger=log)
async def update_node_outputs(
    app: web.Application,
    user_id: UserID,
    project_uuid: ProjectID,
    node_uuid: NodeID,
    outputs: dict,
    run_hash: str | None,
    node_errors: list[ErrorDict] | None,
    *,
    ui_changed_keys: set[str] | None,
) -> None:
    # the new outputs might be {}, or {key_name: payload}
    project, keys_changed = await projects_api.update_project_node_outputs(
        app,
        user_id,
        project_uuid,
        node_uuid,
        new_outputs=outputs,
        new_run_hash=run_hash,
    )

    await projects_api.notify_project_node_update(
        app, project, node_uuid, errors=node_errors
    )
    # get depending node and notify for these ones as well
    depending_node_uuids = await project_get_depending_nodes(project, node_uuid)
    await logged_gather(
        *[
            projects_api.notify_project_node_update(app, project, nid, errors=None)
            for nid in depending_node_uuids
        ]
    )

    # changed keys are coming from two sources:
    # 1. updates to ports done by UI services
    # 2. updates to ports done other services
    #
    # In the 1. case `keys_changed` will be empty since the version stored in the
    # database will be the same as the as the one in the notification. No key change
    # will be reported (in the past a side effect was causing to detect a key change,
    # but it was now removed).
    # When the project is updated and after the workbench was stored in the db,
    # this method will be invoked with the `ui_changed_keys` containing all
    # the keys which have changed.

    keys: list[str] = (
        keys_changed
        if ui_changed_keys is None
        else list(ui_changed_keys | set(keys_changed))
    )

    # fire&forget to notify connected nodes to retrieve its inputs **if necessary**
    await projects_api.post_trigger_connected_service_retrieve(
        app=app, project=project, updated_node_uuid=f"{node_uuid}", changed_keys=keys
    )


async def update_frontend_outputs(
    app: web.Application,
    user_id: UserID,
    project_uuid: ProjectID,
    old_project: dict[str, Any],
    new_project: dict[str, Any],
) -> None:
    old_workbench = old_project["workbench"]
    new_workbench = new_project["workbench"]
    frontend_nodes_update_tasks: deque[Coroutine] = deque()

    for node_key, node in new_workbench.items():
        old_node = old_workbench.get(node_key)
        if not old_node:
            continue

        # check if there were any changes in the outputs of
        # frontend services
        # NOTE: for now only file-picker is handled
        outputs_changes: set[str] = get_frontend_node_outputs_changes(
            new_node=node, old_node=old_node
        )

        if len(outputs_changes) > 0:
            frontend_nodes_update_tasks.append(
                update_node_outputs(
                    app=app,
                    user_id=user_id,
                    project_uuid=project_uuid,
                    node_uuid=node_key,
                    outputs=node.get("outputs", {}),
                    run_hash=None,
                    node_errors=None,
                    ui_changed_keys=outputs_changes,
                )
            )

    for task_index, frontend_node_update_task in enumerate(frontend_nodes_update_tasks):
        fire_and_forget_task(
            frontend_node_update_task,
            task_suffix_name=f"frontend_node_update_task_{task_index}",
            fire_and_forget_tasks_collection=app[APP_FIRE_AND_FORGET_TASKS_KEY],
        )
