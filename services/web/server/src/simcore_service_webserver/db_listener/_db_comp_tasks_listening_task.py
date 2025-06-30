"""this module creates a background task that monitors changes in the database.
First a procedure is registered in postgres that gets triggered whenever the outputs
of a record in comp_task table is changed.
"""

import asyncio
import datetime
import logging
from collections.abc import AsyncIterator
from typing import Final, NoReturn, cast

from aiohttp import web
from aiopg.sa.connection import SAConnection
from aiopg.sa.result import RowProxy
from models_library.errors import ErrorDict
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from models_library.projects_state import RunningState
from pydantic.types import PositiveInt
from servicelib.background_task import periodic_task
from servicelib.logging_utils import log_catch
from simcore_postgres_database.models.comp_tasks import comp_tasks
from simcore_postgres_database.webserver_models import DB_CHANNEL_NAME, projects
from sqlalchemy.sql import select

from ..db.plugin import get_database_engine
from ..projects import _projects_service, exceptions
from ..projects.nodes_utils import update_node_outputs
from ._models import CompTaskNotificationPayload
from ._utils import convert_state_from_db

_LISTENING_TASK_BASE_SLEEPING_TIME_S: Final[int] = 1
_logger = logging.getLogger(__name__)


async def _get_project_owner(
    conn: SAConnection, project_uuid: ProjectID
) -> PositiveInt:
    the_project_owner: PositiveInt | None = await conn.scalar(
        select(projects.c.prj_owner).where(projects.c.uuid == f"{project_uuid}")
    )
    if not the_project_owner:
        raise exceptions.ProjectOwnerNotFoundError(project_uuid=project_uuid)
    return the_project_owner


async def _update_project_state(
    app: web.Application,
    user_id: PositiveInt,
    project_uuid: ProjectID,
    node_uuid: NodeID,
    new_state: RunningState,
    node_errors: list[ErrorDict] | None,
) -> None:
    project = await _projects_service.update_project_node_state(
        app, user_id, project_uuid, node_uuid, new_state
    )

    await _projects_service.notify_project_node_update(
        app, project, node_uuid, node_errors
    )
    await _projects_service.notify_project_state_update(app, project)


async def _get_changed_comp_task_row(
    conn: SAConnection, task_id: PositiveInt
) -> RowProxy | None:
    result = await conn.execute(
        select(comp_tasks).where(comp_tasks.c.task_id == task_id)
    )
    return cast(RowProxy | None, await result.fetchone())


async def _handle_db_notification(
    app: web.Application, payload: CompTaskNotificationPayload, conn: SAConnection
) -> None:
    with log_catch(_logger, reraise=False):
        try:
            the_project_owner = await _get_project_owner(conn, payload.project_id)
            changed_row = await _get_changed_comp_task_row(conn, payload.task_id)
            if not changed_row:
                _logger.warning(
                    "No comp_tasks row found for project_id=%s node_id=%s",
                    payload.project_id,
                    payload.node_id,
                )
                return

            if any(f in payload.changes for f in ["outputs", "run_hash"]):
                await update_node_outputs(
                    app,
                    the_project_owner,
                    payload.project_id,
                    payload.node_id,
                    changed_row.outputs,
                    changed_row.run_hash,
                    node_errors=changed_row.errors,
                    ui_changed_keys=None,
                )

            if "state" in payload.changes and (changed_row.state is not None):
                await _update_project_state(
                    app,
                    the_project_owner,
                    payload.project_id,
                    payload.node_id,
                    convert_state_from_db(changed_row.state),
                    node_errors=changed_row.errors,
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


async def _listen(app: web.Application) -> NoReturn:
    listen_query = f"LISTEN {DB_CHANNEL_NAME};"
    db_engine = get_database_engine(app)
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
            payload = CompTaskNotificationPayload.model_validate_json(
                notification.payload
            )
            _logger.debug("received update from database: %s", f"{payload=}")
            await _handle_db_notification(app, payload, conn)


async def create_comp_tasks_listening_task(app: web.Application) -> AsyncIterator[None]:
    async with periodic_task(
        _listen,
        interval=datetime.timedelta(seconds=_LISTENING_TASK_BASE_SLEEPING_TIME_S),
        task_name="computation db listener",
        app=app,
    ):
        yield
