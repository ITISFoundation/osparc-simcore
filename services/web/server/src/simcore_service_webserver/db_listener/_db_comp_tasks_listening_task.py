"""Background task that projects comp_tasks changes into projects_nodes.

Uses a transactional outbox pattern: comp_tasks trigger inserts into outbox_events
on every meaningful change. This task claims, processes, and deletes outbox events
in short transactions, tolerating horizontal scaling via FOR UPDATE SKIP LOCKED.

The event row is deleted only after successful processing (at-least-once delivery):
the FOR UPDATE lock is held for the whole claim-process-delete transaction, so a
crash or failure rolls the claim back and any replica can re-claim the event.
Failed attempts are counted on the row itself; events that exceed the maximum
number of attempts are dead-lettered (skipped by claims, kept for post-mortem).

Each event records the comp_tasks columns that changed (`changed_columns`), so the
projection only pushes what actually changed, like the previous LISTEN/NOTIFY
payload did.
"""

import asyncio
import contextlib
import logging
from typing import Final, NoReturn

from aiohttp import web
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from models_library.projects_state import RunningState
from models_library.users import UserID
from pydantic.types import PositiveInt
from simcore_postgres_database.models.comp_tasks import comp_tasks
from simcore_postgres_database.models.outbox_events import outbox_events
from simcore_postgres_database.utils_repos import transaction_context
from simcore_postgres_database.webserver_models import DB_CHANNEL_NAME, projects
from sqlalchemy.engine import Row
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine
from sqlalchemy.sql import select

from ..db.plugin import get_asyncpg_engine
from ..projects import _projects_service, exceptions
from ..projects.nodes_utils import update_node_outputs
from ._utils import convert_state_from_db

_OUTBOX_POLL_INTERVAL_S: Final[int] = 30
_MAX_ATTEMPTS: Final[int] = 10
_MAX_CONSECUTIVE_FAILURES: Final[int] = 3

# a change to any of these columns must refresh the node's outputs projection
_OUTPUTS_CHANGED_COLUMNS: Final[frozenset[str]] = frozenset({"outputs", "run_hash"})

# last_error is a Text column, but keep the stored message bounded anyway
_LAST_ERROR_MAX_LEN: Final[int] = 500

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
    conn: AsyncConnection,
    task_id: int,
    changed_columns: frozenset[str],
) -> None:
    """Project a comp_tasks change onto projects_nodes.

    Only the columns reported by the event's `changed_columns` are projected
    (mirroring the previous LISTEN/NOTIFY payload semantics): pushing state
    or outputs the UI already has would produce needless socketio notifications.
    The projection itself reads the *current* row, so it stays idempotent when
    several events coalesce into one processed state.
    """
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
        if changed_columns & _OUTPUTS_CHANGED_COLUMNS:
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

        if "state" in changed_columns and (comp_task_row.state is not None):
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


async def _claim_and_process_one_outbox_event(
    app: web.Application,
    engine: AsyncEngine,
) -> bool | None:
    """Claim, process, and delete one pending outbox event (at-least-once delivery).

    The whole claim-process-delete cycle runs in a single transaction, so the
    `FOR UPDATE SKIP LOCKED` lock is held while the event is processed: exactly one
    replica can work on a given event, and a crash or failure rolls the claim back,
    leaving the event in place for any replica to re-claim.

    Returns True when an event was processed and deleted, False when processing an
    event failed (attempt recorded on the row), and None when no claimable event
    is pending.

    NOTE: processing runs while the transaction (and row lock) is open, so it must
    remain short-lived (DB updates + socketio notifications only).
    """
    processing_error: tuple[Row, Exception] | None = None

    try:
        async with transaction_context(engine) as conn:
            result = await conn.execute(
                select(outbox_events)
                .where(outbox_events.c.attempts < _MAX_ATTEMPTS)
                .order_by(outbox_events.c.modified, outbox_events.c.id)
                .with_for_update(skip_locked=True)
                .limit(1)
            )
            row = result.fetchone()
            if row is None:
                return None

            _logger.debug("Claimed outbox event %d (aggregate_id=%s)", row.id, row.aggregate_id)
            try:
                await _process_outbox_event(
                    app,
                    conn,
                    int(row.aggregate_id),
                    frozenset(row.changed_columns or []),
                )
            except Exception as exc:
                # re-raise so the context manager rolls back the claim: this releases
                # the row lock and undoes any partial projection, leaving the event
                # in place for any replica to re-claim.
                processing_error = (row, exc)
                raise

            # success: remove the event within the same transaction (releases the lock)
            await conn.execute(outbox_events.delete().where(outbox_events.c.id == row.id))
    except Exception:  # pylint: disable=broad-exception-caught
        if processing_error is None:
            raise

    if processing_error is not None:
        failed_row, failed_exc = processing_error
        await _record_failed_attempt(engine, failed_row, failed_exc)
        return False
    return True


async def _record_failed_attempt(engine: AsyncEngine, row: Row, error: Exception) -> None:
    """Record a failed processing attempt on the event row (separate transaction).

    The UPDATE bumps `attempts`/`last_error` and (via the auto-update trigger)
    refreshes `modified`, which pushes the event to the back of the oldest-first
    queue and thereby spaces out retries.
    Once `attempts` reaches the maximum, the event is dead-lettered: claims skip
    it and it remains in the table for post-mortem inspection.
    """
    async with transaction_context(engine) as conn:
        await conn.execute(
            outbox_events.update()
            .values(
                attempts=outbox_events.c.attempts + 1,
                last_error=str(error)[:_LAST_ERROR_MAX_LEN],
            )
            .where(outbox_events.c.id == row.id)
        )

    if row.attempts + 1 >= _MAX_ATTEMPTS:
        _logger.error(
            "Outbox event %d (kind=%s, aggregate_id=%s) dead-lettered after %d attempts; last error: %s",
            row.id,
            row.kind,
            row.aggregate_id,
            _MAX_ATTEMPTS,
            error,
        )
    else:
        _logger.warning(
            "Outbox event %d (aggregate_id=%s) failed attempt %d/%d, will retry: %s",
            row.id,
            row.aggregate_id,
            row.attempts + 1,
            _MAX_ATTEMPTS,
            error,
        )


async def _claim_and_process_outbox_events(app: web.Application, engine: AsyncEngine) -> None:
    """Drain pending outbox events, one at a time, safe for concurrent replicas.

    The drain stops early after too many consecutive failures so that a poison
    event cannot spin the loop and starve the wake-up/poll cycle; the remaining
    events are retried on the next cycle.
    """
    consecutive_failures = 0
    while True:
        outcome = await _claim_and_process_one_outbox_event(app, engine)
        if outcome is None:
            return  # queue drained
        if outcome:
            consecutive_failures = 0
        else:
            consecutive_failures += 1
            if consecutive_failures >= _MAX_CONSECUTIVE_FAILURES:
                _logger.warning(
                    "Stopping outbox drain after %d consecutive failures; will retry on next cycle",
                    consecutive_failures,
                )
                return


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
                except Exception:  # pylint: disable=broad-exception-caught
                    _logger.exception("Error draining outbox events")
                    # Continue looping; reconnect will happen on next timeout if needed
        finally:
            await asyncpg_conn.remove_listener(DB_CHANNEL_NAME, _on_wakeup)
