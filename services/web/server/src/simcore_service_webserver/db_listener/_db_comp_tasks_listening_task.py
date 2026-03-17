"""this module creates a background task that monitors changes in the database.
First a procedure is registered in postgres that gets triggered whenever the outputs
of a record in comp_task table is changed.
"""

import asyncio
import datetime
import logging
from collections.abc import AsyncIterator
from typing import Final, NoReturn

import asyncpg
from aiohttp import web
from models_library.errors import ErrorDict
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from models_library.projects_state import RunningState
from pydantic.types import PositiveInt
from servicelib.background_task import periodic_task
from simcore_postgres_database.models.comp_tasks import comp_tasks
from simcore_postgres_database.webserver_models import DB_CHANNEL_NAME, projects
from sqlalchemy.engine import Row
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine
from sqlalchemy.sql import select

from ..db.plugin import get_asyncpg_engine
from ..db.settings import get_plugin_settings
from ..projects import _projects_service, exceptions
from ..projects.nodes_utils import update_node_outputs
from ._models import CompTaskNotificationPayload
from ._utils import convert_state_from_db

_LISTENING_TASK_BASE_SLEEPING_TIME_S: Final[int] = 1
_logger = logging.getLogger(__name__)


async def _get_project_owner(conn: AsyncConnection, project_uuid: ProjectID) -> PositiveInt:
    the_project_owner: PositiveInt | None = (
        await conn.execute(select(projects.c.prj_owner).where(projects.c.uuid == f"{project_uuid}"))
    ).scalar_one_or_none()
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
        app,
        user_id,
        project_uuid,
        node_uuid,
        new_state,
        client_session_id=None,  # <-- The trigger for this update is not from the UI (its db listener)
    )

    await _projects_service.notify_project_node_update(app, project, node_uuid, node_errors)

    await _projects_service.notify_project_state_update(app, project)


async def _get_changed_comp_task_row(conn: AsyncConnection, task_id: PositiveInt) -> Row | None:
    result = await conn.execute(select(comp_tasks).where(comp_tasks.c.task_id == task_id))
    return result.fetchone()


async def _handle_db_notification(
    app: web.Application, payload: CompTaskNotificationPayload, engine: AsyncEngine
) -> None:
    try:
        async with engine.connect() as conn:
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
                client_session_id=None,  # <-- The trigger for this update is not from the UI (its db listener)
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
    engine = get_asyncpg_engine(app)
    settings = get_plugin_settings(app)

    # Use a dedicated raw asyncpg connection for LISTEN/NOTIFY.
    # SQLAlchemy's connection wrapper does not support asyncpg's callback-based
    # notification delivery, so we create a standalone asyncpg connection.
    notifications: asyncio.Queue[str] = asyncio.Queue()

    def _on_notification(
        _conn: object,
        _pid: int,
        _channel: str,
        payload: str,
    ) -> None:
        notifications.put_nowait(payload)

    asyncpg_conn = await asyncpg.connect(dsn=settings.dsn)
    try:
        # Use asyncpg's native connection.add_listener(channel, callback) for event-driven notifications
        # (replaces polling — more efficient)
        await asyncpg_conn.add_listener(DB_CHANNEL_NAME, _on_notification)
        try:
            while True:
                try:
                    raw_payload = await asyncio.wait_for(
                        notifications.get(),
                        timeout=_LISTENING_TASK_BASE_SLEEPING_TIME_S,
                    )
                except TimeoutError:
                    if asyncpg_conn.is_closed():
                        msg = "connection with database is closed!"
                        raise ConnectionError(msg) from None
                    continue

                payload = CompTaskNotificationPayload.model_validate_json(raw_payload)
                _logger.debug("received update from database: %s", f"{payload=}")
                await _handle_db_notification(app, payload, engine)
        finally:
            if not asyncpg_conn.is_closed():
                await asyncpg_conn.remove_listener(DB_CHANNEL_NAME, _on_notification)
    finally:
        if not asyncpg_conn.is_closed():
            await asyncpg_conn.close()


async def create_comp_tasks_listening_task(app: web.Application) -> AsyncIterator[None]:
    async with periodic_task(
        _listen,
        interval=datetime.timedelta(seconds=_LISTENING_TASK_BASE_SLEEPING_TIME_S),
        task_name="computation db listener",
        app=app,
    ):
        yield
