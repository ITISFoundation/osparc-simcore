"""this module creates a background task that monitors changes in the database.
First a procedure is registered in postgres that gets triggered whenever the outputs
of a record in comp_task table is changed.
"""
import asyncio
import json
import logging
from pprint import pformat
from typing import Dict

from aiohttp import web
from aiopg.sa import Engine
from servicelib.application_keys import APP_DB_ENGINE_KEY
from simcore_postgres_database.webserver_models import DB_CHANNEL_NAME, projects
from sqlalchemy.sql import select

from .projects import projects_api, projects_exceptions

log = logging.getLogger(__name__)

OUTPUT_KEYS_TO_COMPARE = ["path", "store"]


def _is_output_changed(current_outputs: Dict, new_outputs: Dict) -> bool:
    if new_outputs != current_outputs:
        if not current_outputs:
            return True
        for port_key in new_outputs:
            if port_key not in current_outputs:
                return True
            if isinstance(new_outputs[port_key], dict):
                if any(
                    current_outputs[port_key][x] != new_outputs[port_key][x]
                    for x in OUTPUT_KEYS_TO_COMPARE
                ):
                    return True
            if new_outputs[port_key] != current_outputs[port_key]:
                return True
    return False


def _is_state_changed(current_state: str, new_state: str) -> bool:
    return current_state != new_state


from .computation_api import convert_state_from_db


async def _update_project_node_and_notify_if_needed(
    app: web.Application, project: Dict, new_node_data: Dict, user_id: int
) -> None:
    log.debug(
        "Received update from comp_task update from DB: %s", pformat(new_node_data)
    )
    node_uuid = new_node_data["node_id"]
    project_uuid = new_node_data["project_id"]

    if node_uuid not in project["workbench"]:
        raise projects_exceptions.NodeNotFoundError(project_uuid, node_uuid)

    current_outputs = project["workbench"][node_uuid].get("outputs")
    if _is_output_changed(current_outputs, new_node_data["outputs"]):
        project = await projects_api.update_project_node_outputs(
            app,
            user_id,
            project_uuid,
            node_uuid,
            data=new_node_data["outputs"],
        )
        log.debug(
            "Updated node outputs from %s to %s",
            pformat(current_outputs or ""),
            pformat(new_node_data["outputs"]),
        )
        await projects_api.notify_project_node_update(app, project, node_uuid)

    current_state = project["workbench"][node_uuid].get("state")
    new_state = convert_state_from_db(new_node_data["state"]).value
    if _is_state_changed(current_state, new_state):
        project = await projects_api.update_project_node_state(
            app, user_id, project_uuid, node_uuid, new_state
        )
        log.debug(
            "Updated node state from %s to %s",
            pformat(current_state or ""),
            pformat(new_state),
        )
        await projects_api.notify_project_node_update(app, project, node_uuid)
        await projects_api.notify_project_state_update(app, project)


async def listen(app: web.Application):
    listen_query = f"LISTEN {DB_CHANNEL_NAME};"
    db_engine: Engine = app[APP_DB_ENGINE_KEY]
    async with db_engine.acquire() as conn:
        await conn.execute(listen_query)

        while True:
            msg = await conn.connection.notifies.get()

            # Changes on comp_tasks.outputs of non-frontend task
            log.debug("DB comp_tasks.outputs/state updated: <- %s", msg.payload)
            task_data = json.loads(msg.payload)["data"]
            task_output = task_data["outputs"]
            log.debug("NEW NODE DATA: %s", pformat(task_output))
            project_uuid = task_data["project_id"]

            # FIXME: we do not know who triggered these changes. we assume the user had the rights to do so
            # therefore we'll use the prj_owner user id. This should be fixed when the new sidecar comes in
            # and comp_tasks/comp_pipeline get deprecated.

            # find the user(s) linked to that project
            the_project_owner = await conn.scalar(
                select([projects.c.prj_owner]).where(projects.c.uuid == project_uuid)
            )
            if not the_project_owner:
                log.warning(
                    "Project %s was not found and cannot be updated", project_uuid
                )
                continue

            # update the project if necessary
            project = await projects_api.get_project_for_user(
                app, project_uuid, the_project_owner, include_state=True
            )
            # Update the project outputs
            try:
                await _update_project_node_and_notify_if_needed(
                    app, project, task_data, the_project_owner
                )

            except projects_exceptions.ProjectNotFoundError as exc:
                log.warning(
                    "Project %s was not found and cannot be updated", exc.project_uuid
                )
                continue
            except projects_exceptions.NodeNotFoundError as exc:
                log.warning(
                    "Node %s ib project %s not found and cannot be updated",
                    exc.node_uuid,
                    exc.project_uuid,
                )
                continue


async def comp_tasks_listening_task(app: web.Application) -> None:
    log.info("starting comp_task db listening task...")
    while True:
        try:
            log.info("listening to comp_task events...")
            await listen(app)
        except asyncio.CancelledError:
            # we are closing the app..
            return
        except Exception:  # pylint: disable=broad-except
            log.exception(
                "caught unhandled comp_task db listening task exception, restarting...",
                exc_info=True,
            )


async def setup_comp_tasks_listening_task(app: web.Application):
    task = asyncio.get_event_loop().create_task(comp_tasks_listening_task(app))
    yield
    task.cancel()
    await task


def setup(app: web.Application):
    app.cleanup_ctx.append(setup_comp_tasks_listening_task)
