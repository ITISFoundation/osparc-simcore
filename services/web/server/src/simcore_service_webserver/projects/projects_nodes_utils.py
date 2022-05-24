import logging
from typing import Any, Optional

from aiohttp import web
from models_library.errors import ErrorDict
from pydantic.types import PositiveInt
from servicelib.logging_utils import log_decorator
from servicelib.utils import logged_gather

log = logging.getLogger(__name__)


async def project_get_depending_nodes(
    project: dict[str, Any], node_uuid: str
) -> set[str]:
    depending_node_uuids = set()
    for dep_node_uuid, dep_node_data in project.get("workbench", {}).items():
        for dep_node_inputs_key_data in dep_node_data.get("inputs", {}).values():
            if (
                isinstance(dep_node_inputs_key_data, dict)
                and dep_node_inputs_key_data.get("nodeUuid") == node_uuid
            ):
                depending_node_uuids.add(dep_node_uuid)

    return depending_node_uuids


@log_decorator(logger=log)
async def update_node_outputs(
    app: web.Application,
    user_id: PositiveInt,
    project_uuid: str,
    node_uuid: str,
    outputs: dict,
    run_hash: Optional[str],
    node_errors: Optional[list[ErrorDict]],
    *,
    ui_changed_keys: Optional[set[str]],
) -> None:
    # FIXME: below relative import needs to be resolved
    # https://github.com/ITISFoundation/osparc-simcore/issues/3069
    # unsure how to deal with this circular dependency
    # this function is called from:
    # - `projects/projects_db.py`
    # - `computation_comp_tasks_listening_task.py` (was originally here)
    from . import projects_api

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
        app, project, f"{node_uuid}", errors=node_errors
    )
    # get depending node and notify for these ones as well
    depending_node_uuids = await project_get_depending_nodes(project, f"{node_uuid}")
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

    # notify
    await projects_api.post_trigger_connected_service_retrieve(
        app=app, project=project, updated_node_uuid=node_uuid, changed_keys=keys
    )
