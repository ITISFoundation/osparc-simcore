"""this module creates a background task that monitors changes in the database.
First a procedure is registered in postgres that gets triggered whenever the outputs
of a record in comp_task table is changed.
"""
import asyncio
import json
import logging
from collections.abc import AsyncIterator
from contextlib import suppress
from dataclasses import dataclass
from typing import Final, NoReturn

from aiohttp import web
from aiopg.sa import Engine
from aiopg.sa.connection import SAConnection
from models_library.errors import ErrorDict
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from models_library.projects_state import RunningState
from pydantic.types import PositiveInt
from servicelib.aiohttp.application_keys import APP_DB_ENGINE_KEY
from simcore_postgres_database.webserver_models import DB_CHANNEL_NAME, projects
from sqlalchemy.sql import select

from ..projects import exceptions, projects_api
from ..projects.nodes_utils import update_node_outputs
from ._utils import convert_state_from_db

_LISTENING_TASK_BASE_SLEEPING_TIME_S: Final[int] = 1
_logger = logging.getLogger(__name__)


async def _get_project_owner(conn: SAConnection, project_uuid: str) -> PositiveInt:
    the_project_owner: PositiveInt | None = await conn.scalar(
        select(projects.c.prj_owner).where(projects.c.uuid == project_uuid)
    )
    if not the_project_owner:
        raise exceptions.ProjectOwnerNotFoundError(project_uuid)
    return the_project_owner


async def _update_project_state(
    app: web.Application,
    user_id: PositiveInt,
    project_uuid: ProjectID,
    node_uuid: NodeID,
    new_state: RunningState,
    node_errors: list[ErrorDict] | None,
) -> None:
    project = await projects_api.update_project_node_state(
        app, user_id, project_uuid, node_uuid, new_state
    )

    await projects_api.notify_project_node_update(app, project, node_uuid, node_errors)
    await projects_api.notify_project_state_update(app, project)


@dataclass(frozen=True)
class _CompTaskNotificationPayload:
    action: str
    data: dict
    changes: dict
    table: str


async def _handle_db_notification(
    app: web.Application, payload: _CompTaskNotificationPayload, conn: SAConnection
) -> None:
    task_data = payload.data
    task_changes = payload.changes

    project_uuid = task_data.get("project_id", None)
    node_uuid = task_data.get("node_id", None)
    if any(x is None for x in [project_uuid, node_uuid]):
        _logger.warning(
            "comp_tasks row is corrupted. TIP: please check DB entry containing '%s'",
            f"{task_data=}",
        )
        return

    assert project_uuid  # nosec
    assert node_uuid  # nosec

    try:
        # NOTE: we need someone with the rights to modify that project. the owner is one.
        # find the user(s) linked to that project
        the_project_owner = await _get_project_owner(conn, project_uuid)

        if any(f in task_changes for f in ["outputs", "run_hash"]):
            new_outputs = task_data.get("outputs", {})
            new_run_hash = task_data.get("run_hash", None)

            await update_node_outputs(
                app,
                the_project_owner,
                ProjectID(project_uuid),
                NodeID(node_uuid),
                new_outputs,
                new_run_hash,
                node_errors=task_data.get("errors", None),
                ui_changed_keys=None,
            )

        if "state" in task_changes:
            new_state = convert_state_from_db(task_data["state"])
            await _update_project_state(
                app,
                the_project_owner,
                ProjectID(project_uuid),
                NodeID(node_uuid),
                new_state,
                node_errors=task_data.get("errors", None),
            )

    except exceptions.ProjectNotFoundError as exc:
        _logger.warning(
            "Project %s was not found and cannot be updated. Maybe was it deleted?",
            exc.project_uuid,
        )
    except exceptions.ProjectOwnerNotFoundError as exc:
        _logger.warning(
            "Project owner of project %s could not be found, is the project valid?",
            exc.project_uuid,
        )
    except exceptions.NodeNotFoundError as exc:
        _logger.warning(
            "Node %s of project %s not found and cannot be updated. Maybe was it deleted?",
            exc.node_uuid,
            exc.project_uuid,
        )


async def _listen(app: web.Application, db_engine: Engine) -> NoReturn:
    listen_query = f"LISTEN {DB_CHANNEL_NAME};"

    async with db_engine.acquire() as conn:
        assert conn.connection  # nosec
        await conn.execute(listen_query)

        while True:
            # NOTE: instead of using await get() we check first if the connection was closed
            # since aiopg does not reset the await in such a case (if DB was restarted or so)
            # see aiopg issue: https://github.com/aio-libs/aiopg/pull/559#issuecomment-826813082
            if conn.closed:
                msg = "connection with database is closed!"
                raise ConnectionError(msg)
            if conn.connection.notifies.empty():
                await asyncio.sleep(_LISTENING_TASK_BASE_SLEEPING_TIME_S)
                continue
            notification = conn.connection.notifies.get_nowait()
            # get the data and the info on what changed
            payload = _CompTaskNotificationPayload(**json.loads(notification.payload))
            _logger.debug("received update from database: %s", f"{payload=}")
            await _handle_db_notification(app, payload, conn)


async def _comp_tasks_listening_task(app: web.Application) -> None:
    _logger.info("starting comp_task db listening task...")
    while True:
        try:
            # create a special connection here
            db_engine = app[APP_DB_ENGINE_KEY]
            _logger.info("listening to comp_task events...")
            await _listen(app, db_engine)
        except asyncio.CancelledError:  # noqa: PERF203
            # we are closing the app..
            _logger.info("cancelled comp_tasks events")
            raise
        except Exception:  # pylint: disable=broad-except
            _logger.exception(
                "caught unhandled comp_task db listening task exception, restarting...",
            )
            # wait a bit and try restart the task
            await asyncio.sleep(3)


async def create_comp_tasks_listening_task(app: web.Application) -> AsyncIterator[None]:
    task = asyncio.create_task(
        _comp_tasks_listening_task(app), name="computation db listener"
    )
    _logger.debug("comp_tasks db listening task created %s", f"{task=}")

    yield

    _logger.debug("cancelling comp_tasks db listening %s task...", f"{task=}")
    task.cancel()
    _logger.debug("waiting for comp_tasks db listening %s to stop", f"{task=}")
    with suppress(asyncio.CancelledError):
        await task
    _logger.debug(
        "waiting for comp_tasks db listening %s to stop completed", f"{task=}"
    )
