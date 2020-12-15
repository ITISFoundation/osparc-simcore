"""this module creates a background task that monitors changes in the database.
First a procedure is registered in postgres that gets triggered whenever the outputs
of a record in comp_task table is changed.
"""
import asyncio
import json
import logging
from pprint import pformat
from typing import Dict, List

from aiohttp import web
from aiopg.sa import Engine
from aiopg.sa.connection import SAConnection
from models_library.projects import ProjectID
from models_library.projects_nodes import NodeID
from models_library.projects_state import RunningState
from pydantic.types import PositiveInt
from servicelib.application_keys import APP_DB_ENGINE_KEY
from servicelib.logging_utils import log_decorator
from simcore_postgres_database.webserver_models import DB_CHANNEL_NAME, projects
from sqlalchemy.sql import select

from .computation_api import convert_state_from_db
from .projects import projects_api, projects_exceptions

log = logging.getLogger(__name__)


@log_decorator(logger=log)
async def _get_project_owner(
    conn: SAConnection, project_uuid: ProjectID
) -> PositiveInt:
    the_project_owner = await conn.scalar(
        select([projects.c.prj_owner]).where(projects.c.uuid == project_uuid)
    )
    if not the_project_owner:
        raise projects_exceptions.ProjectOwnerNotFoundError(project_uuid)
    return the_project_owner


@log_decorator(logger=log)
async def _update_project_state(
    app: web.Application,
    user_id: PositiveInt,
    project_uuid: ProjectID,
    node_uuid: NodeID,
    new_state: RunningState,
) -> None:
    project = await projects_api.update_project_node_state(
        app, user_id, project_uuid, node_uuid, new_state
    )
    await projects_api.notify_project_node_update(app, project, node_uuid)
    await projects_api.notify_project_state_update(app, project)


@log_decorator(logger=log)
async def _update_project_outputs(
    app: web.Application,
    user_id: PositiveInt,
    project_uuid: ProjectID,
    node_uuid: NodeID,
    outputs: Dict,
) -> None:
    changed_keys: List[str] = list(outputs.keys())
    if not changed_keys:
        return

    project = await projects_api.update_project_node_outputs(
        app,
        user_id,
        project_uuid,
        node_uuid,
        data=outputs,
    )

    await projects_api.notify_project_node_update(app, project, node_uuid)
    await projects_api.trigger_connected_service_retrieve(
        app, project, node_uuid, changed_keys
    )


async def listen(app: web.Application):
    listen_query = f"LISTEN {DB_CHANNEL_NAME};"
    db_engine: Engine = app[APP_DB_ENGINE_KEY]
    async with db_engine.acquire() as conn:
        await conn.execute(listen_query)

        while True:
            # NOTE: this waits for a new notification so the engine is locked here
            notification = await conn.connection.notifies.get()
            log.debug(
                "received update from database: %s", pformat(notification.payload)
            )
            # get the data and the info on what changed
            payload: Dict = json.loads(notification.payload)

            # FIXME: this part should be replaced by a pydantic CompTaskAtDB once it moves to director-v2
            task_data = payload.get("data", {})
            task_changes = payload.get("changes", [])

            if not task_data:
                log.error("task data invalid: %s", pformat(payload))
                continue

            if not task_changes:
                log.error("no changes but still triggered: %s", pformat(payload))
                continue

            project_uuid = task_data.get("project_id", None)
            node_uuid = task_data.get("node_id", None)

            # FIXME: we do not know who triggered these changes. we assume the user had the rights to do so
            # therefore we'll use the prj_owner user id. This should be fixed when the new sidecar comes in
            # and comp_tasks/comp_pipeline get deprecated.
            try:
                # find the user(s) linked to that project
                the_project_owner = await _get_project_owner(conn, project_uuid)

                if "outputs" in task_changes:
                    new_outputs = task_data.get("outputs", {})
                    await _update_project_outputs(
                        app, the_project_owner, project_uuid, node_uuid, new_outputs
                    )

                if "state" in task_changes:
                    new_state = convert_state_from_db(task_data["state"]).value
                    await _update_project_state(
                        app, the_project_owner, project_uuid, node_uuid, new_state
                    )

            except projects_exceptions.ProjectNotFoundError as exc:
                log.warning(
                    "Project %s was not found and cannot be updated. Maybe was it deleted?",
                    exc.project_uuid,
                )
                continue
            except projects_exceptions.ProjectOwnerNotFoundError as exc:
                log.warning(
                    "Project owner of project %s could not be found, is the project valid?",
                    exc.project_uuid,
                )
                continue
            except projects_exceptions.NodeNotFoundError as exc:
                log.warning(
                    "Node %s of project %s not found and cannot be updated. Maybe was it deleted?",
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
