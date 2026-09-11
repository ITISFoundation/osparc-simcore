"""Background task that projects comp_tasks changes into projects_nodes.

Uses a transactional outbox pattern: comp_tasks trigger inserts into outbox_events
on every meaningful change. This task claims, processes, and deletes outbox events
in short transactions, tolerating horizontal scaling via FOR UPDATE SKIP LOCKED.
"""

import asyncio
import contextlib
import datetime
import logging
from collections.abc import AsyncIterator
from typing import Final, NoReturn

from aiohttp import web
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from models_library.projects_state import RunningState
from models_library.users import UserID
from pydantic.types import PositiveInt
from servicelib.background_task import periodic_task
from simcore_postgres_database.models.comp_tasks import comp_tasks
from simcore_postgres_database.models.outbox_events import outbox_events
from simcore_postgres_database.webserver_models import DB_CHANNEL_NAME, projects
from sqlalchemy.engine import Row
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine
from sqlalchemy.sql import select

from ..db.plugin import get_asyncpg_engine
from ..projects import _projects_service, exceptions
from ..projects.nodes_utils import update_node_outputs
from ._utils import convert_state_from_db

_OUTBOX_POLL_INTERVAL_S: Final[int] = 30
_logger = logging.getLogger(__name__)


async def _get_project_owner(conn: AsyncConnection, project_uuid: ProjectID) -> UserID:
    the_project_owner: PositiveInt | None = (
        await conn.execute(select(projects.c.prj_owner).where(projects.c.uuid == f"{project_uuid}"))
    ).scalar_one_or_none()
    if not the_project_owner:
        raise exceptions.ProjectOwnerNotFoundError(project_uuid=project_uuid)
    return UserID(the_project_owner)


async def _get_comp_task_row(conn: AsyncConnection, task_id: PositiveInt) -> Row | None:
    result = await conn.execute(select(comp_tasks).where(comp_tasks.c.task_id == task_id))
    return result.fetchone()


async def _update_project_state(
    app: web.Application,
    user_id: UserID,
    project_uuid: ProjectID,
    node_uuid: NodeID,
    new_state: RunningState,
) -> None:
    project = await _projects_service.update_project_node_state(
        app,
        user_id,
        project_uuid,
        node_uuid,
        new_state,
        client_session_id=None,
    )

    await _projects_service.notify_project_node_update(app, project, node_uuid)

    await _projects_service.notify_project_state_update(app, project)


async def _process_outbox_event(
    app: web.Application,
    engine: AsyncEngine,
    task_id: int,
) -> None:
    """Read the current comp_tasks state and idempotently project it onto projects_nodes."""
    async with engine.connect() as conn:
        comp_task_row = await _get_comp_task_row(conn, task_id)

        if not comp_task_row:
            _logger.warning(
                "comp_tasks row (task_id=%d) not found; skipping stale outbox event",
                task_id,
            )
            return

        project_id = ProjectID(comp_task_row.project_id)
        node_id = NodeID(comp_task_row.node_id)

        try:
            project_owner = await _get_project_owner(conn, project_id)
        except exceptions.ProjectOwnerNotFoundError:
            _logger.warning(
                "project owner not found for project_id=%s; skipping stale outbox event",
                project_id,
            )
            return

    try:
        if comp_task_row.outputs or comp_task_row.run_hash:
            await update_node_outputs(
                app,
                project_owner,
                project_id,
                node_id,
                comp_task_row.outputs or {},
                comp_task_row.run_hash,
                ui_changed_keys=None,
                client_session_id=None,
            )

        if comp_task_row.state:
            await _update_project_state(
                app,
                project_owner,
                project_id,
                node_id,
                convert_state_from_db(comp_task_row.state),
            )
    except exceptions.ProjectNotFoundError:
        _logger.warning(
            "project %s not found; skipping stale outbox event",
            project_id,
        )
    except exceptions.NodeNotFoundError:
        _logger.warning(
            "node %s in project %s not found; skipping stale outbox event",
            node_id,
            project_id,
        )


async def _claim_next_outbox_event(engine: AsyncEngine) -> Row | None:
    """Atomically claim and remove one pending outbox event.

    Combining `FOR UPDATE SKIP LOCKED` with an immediate delete in the same transaction
    guarantees exactly one replica can claim a given event, even when multiple replicas
    poll concurrently (a bare SELECT ... FOR UPDATE releases its lock as soon as the
    transaction ends, which would otherwise let another replica re-claim the same row).
    """
    async with engine.begin() as conn:
        result = await conn.execute(
            select(outbox_events).order_by(outbox_events.c.id).with_for_update(skip_locked=True).limit(1)
        )
        row = result.fetchone()
        if row is None:
            return None
        await conn.execute(outbox_events.delete().where(outbox_events.c.id == row.id))
    return row


async def _requeue_outbox_event(engine: AsyncEngine, row: Row, error: str) -> None:
    """Re-insert a failed event as a new row, keeping track of attempts/last_error."""
    async with engine.begin() as conn:
        await conn.execute(
            outbox_events.insert().values(
                kind=row.kind,
                aggregate_type=row.aggregate_type,
                aggregate_id=row.aggregate_id,
                attempts=row.attempts + 1,
                last_error=error[:500],  # Truncate to DB column limit
            )
        )


async def _claim_and_process_outbox_events(app: web.Application, engine: AsyncEngine) -> None:
    """Drain all pending outbox events, one at a time, safe for concurrent replicas."""
    while True:
        row = await _claim_next_outbox_event(engine)
        if row is None:
            break

        _logger.debug("Claimed outbox event %d (aggregate_id=%s)", row.id, row.aggregate_id)
        try:
            await _process_outbox_event(app, engine, int(row.aggregate_id))
        except Exception as exc:
            _logger.exception("Outbox event %d failed to process, will retry", row.id)
            await _requeue_outbox_event(engine, row, str(exc))
            # Pause briefly before retrying
            await asyncio.sleep(1)


async def _listen_and_poll(app: web.Application) -> NoReturn:
    engine = get_asyncpg_engine(app)

    # Wake-up event: signaled by pg_notify('outbox_wakeup') from trigger
    wakeup_event: asyncio.Event = asyncio.Event()

    def _on_wakeup(
        _conn: object,
        _pid: int,
        _channel: str,
        _payload: str,
    ) -> None:
        wakeup_event.set()

    # Borrow a dedicated connection from the app's shared pool to LISTEN on
    # (asyncpg's callback-based notifications require holding one connection open)
    async with engine.connect() as listen_conn:
        raw_conn = await listen_conn.get_raw_connection()
        asyncpg_conn = raw_conn.driver_connection
        assert asyncpg_conn is not None  # nosec
        await asyncpg_conn.add_listener(DB_CHANNEL_NAME, _on_wakeup)
        try:
            while True:
                # Wait for wakeup OR poll interval timeout
                with contextlib.suppress(TimeoutError):
                    await asyncio.wait_for(
                        wakeup_event.wait(),
                        timeout=_OUTBOX_POLL_INTERVAL_S,
                    )
                wakeup_event.clear()

                # Drain pending outbox events
                try:
                    await _claim_and_process_outbox_events(app, engine)
                except Exception:
                    _logger.exception("Error draining outbox events")
                    # Continue looping; reconnect will happen on next timeout if needed
        finally:
            await asyncpg_conn.remove_listener(DB_CHANNEL_NAME, _on_wakeup)


async def create_comp_tasks_listening_task(app: web.Application) -> AsyncIterator[None]:
    async with periodic_task(
        _listen_and_poll,
        interval=datetime.timedelta(seconds=_OUTBOX_POLL_INTERVAL_S),
        task_name="outbox projector",
        app=app,
    ):
        yield
