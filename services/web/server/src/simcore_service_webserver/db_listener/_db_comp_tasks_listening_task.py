"""Background task that projects comp_tasks changes into projects_nodes.

Uses a transactional outbox pattern: comp_tasks trigger inserts into outbox_events
on every meaningful change. This task claims, processes, and deletes outbox events
in short transactions, tolerating horizontal scaling via FOR UPDATE SKIP LOCKED
plus a per-aggregate advisory lock (pg_try_advisory_xact_lock, keyed on kind +
aggregate_id): no two replicas can ever process events for the same aggregate
concurrently, which is what makes it safe to run this service with more than one
replica.

The event row is deleted only after successful processing (at-least-once delivery):
the FOR UPDATE lock is held for the whole claim-process-delete transaction, so a
crash or failure rolls the claim back and any replica can re-claim the event. Both
the row lock and the advisory lock are released automatically on commit/rollback,
so a crash cannot wedge an aggregate forever.
Failed attempts are counted on the row itself; events that exceed the maximum
number of attempts are dead-lettered (skipped by claims, kept for post-mortem).

Each event records the comp_tasks columns that changed (`changed_columns`), so the
projection only pushes what actually changed, like the previous LISTEN/NOTIFY
payload did. All pending events of the same aggregate are coalesced into a single
projection (union of their changed_columns), so a burst of changes to one task
produces one socketio notification instead of one per event. Claims are scoped to
`DB_OUTBOX_KIND_COMP_TASK_SYNC` since outbox_events is a shared table that other
producers/consumers may use in the future.
"""

import asyncio
import contextlib
import dataclasses
import datetime
import logging
from collections.abc import AsyncGenerator, AsyncIterator
from dataclasses import dataclass
from typing import Final

from aiohttp import web
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from models_library.projects_state import RunningState
from models_library.users import UserID
from pydantic.types import PositiveInt
from servicelib.background_task import periodic_task
from simcore_postgres_database.models.comp_tasks import comp_tasks
from simcore_postgres_database.models.outbox_events import outbox_events
from simcore_postgres_database.utils_repos import transaction_context
from simcore_postgres_database.webserver_models import (
    DB_CHANNEL_NAME,
    DB_OUTBOX_KIND_COMP_TASK_SYNC,
    projects,
)
from sqlalchemy.engine import Row
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine
from sqlalchemy.sql import func, select, tuple_

from ..db.plugin import get_asyncpg_engine
from ..projects import _projects_service, exceptions
from ..projects.nodes_utils import update_node_outputs
from ._utils import convert_state_from_db

_OUTBOX_POLL_INTERVAL_S: Final[int] = 30
_MAX_ATTEMPTS: Final[int] = 10
_MAX_FAILED_AGGREGATES_PER_DRAIN: Final[int] = 3

# size of the FOR UPDATE SKIP LOCKED batch the advisory lock then filters down to one
_CLAIM_CANDIDATE_BATCH: Final[int] = 10

# upper bound on how many pending events of one aggregate are coalesced into a single
# projection per claim; leftovers stay queued and are claimed on the next iteration
_MAX_COALESCE_BATCH: Final[int] = 100

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
    The DB projection re-reads the *current* row, so retries converge to the same
    state; the socketio notifications themselves are not transactional and may be
    re-sent on a retried attempt (at-least-once, not exactly-once).
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


@dataclass(frozen=True, slots=True, kw_only=True)
class _ClaimOutcome:
    """Result of one claim-and-process iteration."""

    success: bool
    kind: str
    aggregate_id: str


async def _claim_and_process_one_outbox_event(
    app: web.Application,
    engine: AsyncEngine,
    exclude_aggregates: set[tuple[str, str]],
) -> _ClaimOutcome | None:
    """Claim, process, and delete every pending event of one aggregate (at-least-once).

    Claiming is two-staged: FOR UPDATE SKIP LOCKED first grabs a small batch of the
    oldest claimable rows (competing consumers across replicas), then a per-aggregate
    advisory lock (pg_try_advisory_xact_lock, keyed on kind + aggregate_id) picks the
    oldest row in that batch whose aggregate isn't already being processed by another
    replica. This guarantees events for the same aggregate are never processed
    concurrently, so socketio notifications for one aggregate can't be emitted out of
    order across replicas. Including kind in the lock key keeps this worker's lock
    namespace separate from other (future) producers that may reuse the same id space.

    Once one event of an aggregate is claimed, all its other pending events are
    co-claimed in the same transaction (FOR UPDATE SKIP LOCKED) and projected once:
    the union of their changed_columns describes everything that happened since the
    last projection, and _process_outbox_event re-reads the current comp_tasks row, so
    a burst of N events for one aggregate fans out a single socketio notification
    instead of N. Rows another replica is currently holding are skipped by the
    co-claim and left for that replica.

    The whole claim-process-delete cycle runs in a single transaction: the row locks
    and the advisory lock are all held while the events are processed, and released
    automatically on commit or rollback.

    ``exclude_aggregates`` is a set of (kind, aggregate_id) pairs the drain wants to
    skip, so an aggregate that already failed in this drain cannot starve the rest of
    the queue.

    Returns the _ClaimOutcome (success flag + the aggregate claimed), or None when no
    event could be claimed -- either the queue is drained, or every candidate's
    aggregate is currently locked by another replica (retried on the next cycle).

    NOTE: processing runs while the transaction (and both locks) is open, so it must
    remain short-lived (DB updates + socketio notifications only).
    """
    processing_error: tuple[_ClaimOutcome, list[int], Exception] | None = None

    try:
        async with transaction_context(engine) as conn:
            claimable = (outbox_events.c.kind == DB_OUTBOX_KIND_COMP_TASK_SYNC) & (
                outbox_events.c.attempts < _MAX_ATTEMPTS
            )
            if exclude_aggregates:
                claimable = claimable & ~tuple_(outbox_events.c.kind, outbox_events.c.aggregate_id).in_(
                    list(exclude_aggregates)
                )

            claim_candidates = (
                select(outbox_events.c.id)
                .where(claimable)
                .order_by(outbox_events.c.modified, outbox_events.c.id)
                .limit(_CLAIM_CANDIDATE_BATCH)
                .with_for_update(skip_locked=True)
                .subquery("claim_candidates")
            )
            result = await conn.execute(
                select(outbox_events)
                .join(claim_candidates, claim_candidates.c.id == outbox_events.c.id)
                .where(
                    # lock namespace must match the claim namespace (kind + aggregate_id):
                    # another producer reusing the same id space must not collide with ours
                    func.pg_try_advisory_xact_lock(
                        func.hashtextextended(outbox_events.c.kind + ":" + outbox_events.c.aggregate_id, 0)
                    )
                )
                .order_by(outbox_events.c.modified, outbox_events.c.id)
                .limit(1)
            )
            row = result.fetchone()
            if row is None:
                return None

            # co-claim every other pending event of the same aggregate: the seed row's
            # lock is already ours (same transaction), other replicas' rows are skipped
            co_claimed = await conn.execute(
                select(outbox_events.c.id, outbox_events.c.changed_columns)
                .where(
                    outbox_events.c.kind == row.kind,
                    outbox_events.c.aggregate_id == row.aggregate_id,
                    outbox_events.c.attempts < _MAX_ATTEMPTS,
                )
                .order_by(outbox_events.c.modified, outbox_events.c.id)
                .limit(_MAX_COALESCE_BATCH)
                .with_for_update(skip_locked=True)
            )
            co_claimed_rows = co_claimed.fetchall()
            claimed_ids = [r.id for r in co_claimed_rows]
            changed_columns = frozenset(col for r in co_claimed_rows for col in (r.changed_columns or []))

            _logger.debug(
                "Claimed %d outbox event(s) (kind=%s aggregate_id=%s)",
                len(claimed_ids),
                row.kind,
                row.aggregate_id,
            )
            outcome = _ClaimOutcome(success=True, kind=row.kind, aggregate_id=row.aggregate_id)
            try:
                await _process_outbox_event(app, conn, int(row.aggregate_id), changed_columns)
            except Exception as exc:
                # re-raise so the context manager rolls back the claim: this releases
                # the row locks and undoes any partial projection, leaving the events
                # in place for any replica to re-claim.
                processing_error = (outcome, claimed_ids, exc)
                raise

            # success: remove all co-claimed events within the same transaction
            await conn.execute(outbox_events.delete().where(outbox_events.c.id.in_(claimed_ids)))
    except Exception:  # pylint: disable=broad-exception-caught
        if processing_error is None:
            raise

    if processing_error is not None:
        failed_outcome, claimed_ids, failed_exc = processing_error
        await _record_failed_attempts(engine, claimed_ids, failed_exc)
        return dataclasses.replace(failed_outcome, success=False)
    return outcome


async def _record_failed_attempts(engine: AsyncEngine, claimed_ids: list[int], error: Exception) -> None:
    """Record a failed processing attempt on every co-claimed event (separate transaction).

    The UPDATE bumps `attempts`/`last_error` and (via the auto-update trigger)
    refreshes `modified`, which pushes the events to the back of the oldest-first
    queue and thereby spaces out retries.
    Once `attempts` reaches the maximum, an event is dead-lettered: claims skip it
    and it remains in the table for post-mortem inspection.
    """
    async with transaction_context(engine) as conn:
        result = await conn.execute(
            outbox_events.update()
            .values(
                attempts=outbox_events.c.attempts + 1,
                last_error=str(error)[:_LAST_ERROR_MAX_LEN],
            )
            .where(outbox_events.c.id.in_(claimed_ids))
            .returning(
                outbox_events.c.id,
                outbox_events.c.kind,
                outbox_events.c.aggregate_id,
                outbox_events.c.attempts,
            )
        )
        updated = result.fetchall()

    for row in updated:
        if row.attempts >= _MAX_ATTEMPTS:
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
                row.attempts,
                _MAX_ATTEMPTS,
                error,
            )


async def _claim_and_process_outbox_events(app: web.Application, engine: AsyncEngine) -> None:
    """Drain pending outbox events, one aggregate at a time, safe for concurrent replicas.

    When processing fails for an aggregate, its (kind, aggregate_id) is excluded from
    the rest of this drain so one poisoned aggregate cannot starve the healthy events
    behind it: the failure is marked on the row (attempt + backoff) and the drain
    moves on to the next aggregate. The drain aborts only after too many aggregates
    have failed *without any success in between* -- that pattern points at broken
    infrastructure (e.g. DB, socketio) rather than one bad event, and continuing
    would just spin. Since excluded aggregates cannot be re-claimed within the drain,
    every counted failure concerns a distinct aggregate; a success resets the count.
    Everything left over is retried on the next wake-up or poll cycle, where the
    failed aggregates become claimable again (with their backoff applied).

    The drain also stops when every claimable event's aggregate is currently locked
    by another replica: the next cycle will retry, by which time that replica is likely done.
    """
    failed_aggregates: set[tuple[str, str]] = set()
    consecutive_failed_aggregates = 0
    while True:
        outcome = await _claim_and_process_one_outbox_event(app, engine, failed_aggregates)
        if outcome is None:
            return  # queue drained, or all remaining aggregates are locked elsewhere
        if outcome.success:
            consecutive_failed_aggregates = 0
        else:
            failed_aggregates.add((outcome.kind, outcome.aggregate_id))
            consecutive_failed_aggregates += 1
            if consecutive_failed_aggregates >= _MAX_FAILED_AGGREGATES_PER_DRAIN:
                _logger.warning(
                    "Stopping outbox drain after %d aggregates failed without a success"
                    " in-between; will retry on next cycle",
                    consecutive_failed_aggregates,
                )
                return


@contextlib.asynccontextmanager
async def with_outbox_wakeup_listener(app: web.Application) -> AsyncGenerator[asyncio.Event]:
    """Holds one pooled connection open to LISTEN on the outbox wake-up channel.

    Yields the event that pg_notify('outbox_wakeup') sets: pass it as the
    `early_wake_up_event` of a periodic drain task, so events are picked up as
    soon as they land instead of waiting for the next poll interval.
    """
    engine = get_asyncpg_engine(app)
    wakeup_event: asyncio.Event = asyncio.Event()

    def _on_wakeup(
        _conn: object,
        _pid: int,
        _channel: str,
        _payload: str,
    ) -> None:
        wakeup_event.set()

    # Borrow a connection from the app's shared pool to LISTEN on
    # (asyncpg's callback-based notifications require holding one connection open)
    async with engine.connect() as listen_conn:
        raw_conn = await listen_conn.get_raw_connection()
        asyncpg_conn = raw_conn.driver_connection
        assert asyncpg_conn is not None  # nosec
        await asyncpg_conn.add_listener(DB_CHANNEL_NAME, _on_wakeup)
        try:
            yield wakeup_event
        finally:
            await asyncpg_conn.remove_listener(DB_CHANNEL_NAME, _on_wakeup)


async def create_comp_tasks_listening_task(app: web.Application) -> AsyncIterator[None]:
    # the LISTEN connection stays open for the task's lifetime and a pg_notify
    # wake-up drains the outbox immediately, instead of waiting for the poll interval
    async with (
        with_outbox_wakeup_listener(app) as wakeup_event,
        periodic_task(
            _claim_and_process_outbox_events,
            interval=datetime.timedelta(seconds=_OUTBOX_POLL_INTERVAL_S),
            task_name="outbox projector",
            early_wake_up_event=wakeup_event,
            app=app,
            engine=get_asyncpg_engine(app),
        ),
    ):
        yield
