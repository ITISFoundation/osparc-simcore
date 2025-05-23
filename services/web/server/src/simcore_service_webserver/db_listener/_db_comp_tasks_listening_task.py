"""this module creates a background task that monitors changes in the database.
First a procedure is registered in postgres that gets triggered whenever the outputs
of a record in comp_task table is changed.
"""

import asyncio
import datetime
import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Final, NoReturn

from aiohttp import web
from aiopg.sa.connection import SAConnection
from common_library.json_serialization import json_loads
from models_library.errors import ErrorDict
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from models_library.projects_state import RunningState
from pydantic.types import PositiveInt
from servicelib.background_task import periodic_task
from simcore_postgres_database.models.comp_tasks import comp_tasks
from simcore_postgres_database.webserver_models import DB_CHANNEL_NAME, projects
from sqlalchemy.sql import select

from ..db.plugin import get_database_engine
from ..projects import _projects_service, exceptions
from ..projects.nodes_utils import update_node_outputs
from ._utils import convert_state_from_db

_LISTENING_TASK_BASE_SLEEPING_TIME_S: Final[int] = 1
_logger = logging.getLogger(__name__)


async def _get_project_owner(conn: SAConnection, project_uuid: str) -> PositiveInt:
    the_project_owner: PositiveInt | None = await conn.scalar(
        select(projects.c.prj_owner).where(projects.c.uuid == project_uuid)
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


@dataclass(frozen=True)
class _CompTaskNotificationPayload:
    action: str
    changes: dict
    table: str
    task_id: str | None = None
    project_id: str | None = None
    node_id: str | None = None


async def _handle_db_notification(
    app: web.Application, payload: _CompTaskNotificationPayload, conn: SAConnection
) -> None:
    project_uuid = payload.project_id
    node_uuid = payload.node_id
    task_changes = payload.changes

    if any(x is None for x in [project_uuid, node_uuid]):
        _logger.warning(
            "comp_tasks row is corrupted. TIP: please check DB entry containing '%s'",
            f"{payload=}",
        )
        return

    assert project_uuid  # nosec
    assert node_uuid  # nosec

    try:
        the_project_owner = await _get_project_owner(conn, project_uuid)

        # Fetch the latest comp_tasks row for this node/project
        result = await conn.execute(
            select(comp_tasks).where(
                (comp_tasks.c.project_id == project_uuid)
                & (comp_tasks.c.node_id == node_uuid)
            )
        )
        row = await result.first()
        if not row:
            _logger.warning(
                "No comp_tasks row found for project_id=%s node_id=%s",
                project_uuid,
                node_uuid,
            )
            return

        if any(f in task_changes for f in ["outputs", "run_hash"]):
            new_outputs = row.outputs if hasattr(row, "outputs") else {}
            new_run_hash = row.run_hash if hasattr(row, "run_hash") else None
            node_errors = row.errors if hasattr(row, "errors") else None
            await update_node_outputs(
                app,
                the_project_owner,
                ProjectID(project_uuid),
                NodeID(node_uuid),
                new_outputs,
                new_run_hash,
                node_errors=node_errors,
                ui_changed_keys=None,
            )

        if "state" in task_changes:
            new_state = row.state if hasattr(row, "state") else None
            if new_state is not None:
                await _update_project_state(
                    app,
                    the_project_owner,
                    ProjectID(project_uuid),
                    NodeID(node_uuid),
                    convert_state_from_db(new_state),
                    node_errors=row.errors if hasattr(row, "errors") else None,
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
            payload = _CompTaskNotificationPayload(**json_loads(notification.payload))
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
