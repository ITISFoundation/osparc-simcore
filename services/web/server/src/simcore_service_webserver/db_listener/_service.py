"""Business logic of the db_listener domain: comp_tasks -> projects_nodes projection.

The comp_tasks DB trigger inserts into outbox_events on every meaningful change
(transactional outbox). This module claims, processes, and deletes those events in
short transactions, tolerating horizontal scaling (the claim/lock mechanics live in
`_repository.py`).

Delivery is at-least-once: the event rows are deleted only after successful
processing, and both the advisory lock and the row locks are held for the whole
claim-process-delete transaction, so a crash or failure rolls the claim back and any
replica can re-claim. The projection re-reads the *current* comp_tasks row, so
retried attempts converge to the same state; the socketio notifications themselves
are not transactional and may be re-sent (at-least-once, not exactly-once). They are
emitted strictly: a real emit failure (e.g. the RabbitMQ-backed socket.io manager is
down) fails the processing and the event is retried, while a room with no members
(e.g. every user disconnected) is a successful no-op and never causes a retry.

Each event records the comp_tasks columns that changed (`changed_columns`), so the
projection only pushes what actually changed, like the previous LISTEN/NOTIFY
payload did. All pending events of the same aggregate are coalesced into a single
projection (union of their changed_columns), so a burst of changes to one task
produces one socketio notification instead of one per event.
Failed attempts are counted on the row itself; events that exceed the maximum
number of attempts are dead-lettered (skipped by claims, kept for post-mortem
until a periodic purge removes them once they age out).
"""

import asyncio
import datetime
import logging
from typing import Final

from aiohttp import web
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from models_library.projects_state import RunningState
from models_library.users import UserID
from simcore_postgres_database.utils_repos import pass_or_acquire_connection, transaction_context
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from ..projects import exceptions
from ..projects.api import (
    notify_project_node_update,
    notify_project_state_update,
    update_node_outputs,
    update_project_node_state,
)
from ._repository import (
    EVENTS_MAX_ATTEMPTS_BEFORE_DEAD_LETTER,
    claim_aggregate,
    delete_expired_dead_letters,
    get_comp_task,
    get_project_owner,
    list_claimable_aggregates,
    record_failed_attempts,
    remove_claimed_events,
)
from ._utils import convert_state_from_db
from .errors import CompTaskNotFoundError, OutboxProcessingError
from .models import (
    DB_OUTBOX_CHANGED_COLUMN_STATE,
    DB_OUTBOX_CHANGED_COLUMNS_OUTPUTS,
    ClaimableAggregate,
    ClaimOutcome,
    FailedAttempt,
)

_MAX_INFRA_FAILED_AGGREGATES_PER_DRAIN: Final[int] = 3

_DEAD_LETTER_RETENTION: Final[datetime.timedelta] = datetime.timedelta(days=30)

# hard deadline on processing one aggregate: the socketio fan-out rides on RabbitMQ and
# a half-open broker connection can stall a publish indefinitely, which would pin the
# claim transaction, its locks, and pool connections until the replica restarts
_PROCESSING_TIMEOUT: Final[datetime.timedelta] = datetime.timedelta(seconds=30)

# only these count towards _MAX_INFRA_FAILED_AGGREGATES_PER_DRAIN: a broken DB/socket
# connection affects every aggregate alike, unlike an application-level bug tied to
# specific rows, which must not halt the rest of an otherwise healthy drain
_INFRA_EXCEPTION_TYPES: Final[tuple[type[Exception], ...]] = (
    DBAPIError,
    OSError,
    TimeoutError,
)

_logger = logging.getLogger(__name__)


async def _update_project_state(
    app: web.Application,
    user_id: UserID,
    project_uuid: ProjectID,
    node_uuid: NodeID,
    new_state: RunningState,
) -> None:
    project = await update_project_node_state(
        app,
        user_id,
        project_uuid,
        node_uuid,
        new_state,
        client_session_id=None,
    )

    # strict: a failed socket.io fan-out (e.g. the RabbitMQ-backed manager is down)
    # must fail the processing so the outbox event is retried, not deleted. Emitting
    # to a room with no members (disconnected users) is a no-op and never raises.
    await notify_project_node_update(app, project, node_uuid, strict=True)

    await notify_project_state_update(app, project, strict=True)


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
    try:
        comp_task = await get_comp_task(conn, task_id)
    except CompTaskNotFoundError:
        _logger.warning(
            "comp_tasks row (task_id=%d) not found; skipping stale outbox event",
            task_id,
        )
        return

    try:
        project_owner = await get_project_owner(conn, comp_task.project_id)
    except exceptions.ProjectOwnerNotFoundError:
        _logger.warning(
            "project owner not found for project_id=%s; skipping stale outbox event",
            comp_task.project_id,
        )
        return

    try:
        if changed_columns & DB_OUTBOX_CHANGED_COLUMNS_OUTPUTS:
            await update_node_outputs(
                app,
                project_owner,
                comp_task.project_id,
                comp_task.node_id,
                comp_task.outputs or {},
                comp_task.run_hash,
                ui_changed_keys=None,
                client_session_id=None,
                strict_notification=True,
            )

        if DB_OUTBOX_CHANGED_COLUMN_STATE in changed_columns and (comp_task.state is not None):
            await _update_project_state(
                app,
                project_owner,
                comp_task.project_id,
                comp_task.node_id,
                convert_state_from_db(comp_task.state),
            )
    except exceptions.ProjectNotFoundError:
        _logger.warning(
            "project %s not found; skipping stale outbox event",
            comp_task.project_id,
        )
    except exceptions.NodeNotFoundError:
        _logger.warning(
            "node %s in project %s not found; skipping stale outbox event",
            comp_task.node_id,
            comp_task.project_id,
        )


async def _claim_and_process_aggregate(
    app: web.Application, engine: AsyncEngine, candidate: ClaimableAggregate
) -> ClaimOutcome | None:
    """Claim, process, and delete every pending event of one aggregate (at-least-once).

    Claiming never locks more than the aggregate it is about to process:
    _repository.claim_aggregate takes the per-aggregate advisory lock and only then
    row-locks the events -- all pending events of the winning aggregate are
    co-claimed (FOR UPDATE SKIP LOCKED) and projected once: the union of their
    changed_columns describes everything that happened since the last projection,
    and _process_outbox_event re-reads the current comp_tasks row, so a burst of N
    events for one aggregate fans out a single socketio notification instead of N.

    The claim-process-delete cycle runs in a single transaction: the advisory lock
    and the winner's row locks are held while the events are processed, and released
    automatically on commit or rollback. A failed projection rolls back only the
    *claim* (locks + pending delete): the projection itself writes through the app's
    repositories and socket.io -- outside this transaction -- so those writes are
    not undone and the retried attempt converges by re-reading the current row
    (at-least-once delivery).

    Returns the ClaimOutcome (success flag + the aggregate claimed), or None when
    the aggregate is currently claimed by another replica or lost its pending events
    in the meantime (the caller moves on to its next candidate).

    NOTE: processing runs while the transaction (and both locks) is open, so it is
    capped by _PROCESSING_TIMEOUT (DB updates + socketio notifications only); a stalled
    publish aborts the claim as an infrastructure failure instead of pinning the locks.
    """
    try:
        async with transaction_context(engine) as conn:
            # win the aggregate (advisory lock + row lock) before processing
            claimed = await claim_aggregate(conn, candidate)
            if claimed is None:
                # locked by another replica, or its events were claimed in-between
                return None

            _logger.debug(
                "Claimed %d outbox event(s) (kind=%s aggregate_id=%s)",
                len(claimed.event_ids),
                claimed.kind,
                claimed.aggregate_id,
            )
            try:
                async with asyncio.timeout(_PROCESSING_TIMEOUT.total_seconds()):
                    await _process_outbox_event(app, conn, int(claimed.aggregate_id), claimed.changed_columns)
            except Exception as exc:
                raise OutboxProcessingError(
                    kind=claimed.kind,
                    aggregate_id=claimed.aggregate_id,
                    event_ids=claimed.event_ids,
                    cause=exc,
                ) from exc

            await remove_claimed_events(conn, claimed.event_ids)
    except OutboxProcessingError as failed:
        updated = await record_failed_attempts(engine, failed.event_ids, failed.cause)
        _log_failed_attempts(updated, failed.cause)
        return ClaimOutcome(
            success=False,
            kind=failed.kind,
            aggregate_id=failed.aggregate_id,
            is_infra_error=isinstance(failed.cause, _INFRA_EXCEPTION_TYPES),
        )

    return ClaimOutcome(success=True, kind=candidate.kind, aggregate_id=candidate.aggregate_id)


async def _claim_and_process_one_outbox_event(
    app: web.Application,
    engine: AsyncEngine,
    exclude_aggregates: set[ClaimableAggregate],
) -> ClaimOutcome | None:
    """Convenience for tests and single-shot claims: scan, then claim the first free
    candidate. The drain reuses a bounded batch instead and must not call this per claim.

    ``exclude_aggregates`` is a set of (kind, aggregate_id) pairs to skip, so an
    aggregate that already failed cannot starve the rest of the queue.
    """
    async with pass_or_acquire_connection(engine) as conn:
        candidates = await list_claimable_aggregates(conn, exclude_aggregates)
    for candidate in candidates:
        outcome = await _claim_and_process_aggregate(app, engine, candidate)
        if outcome is not None:
            return outcome
    return None


def _log_failed_attempts(failed_attempts: list[FailedAttempt], error: Exception) -> None:
    for attempt in failed_attempts:
        if attempt.attempts >= EVENTS_MAX_ATTEMPTS_BEFORE_DEAD_LETTER:
            _logger.error(
                "Outbox event %d (kind=%s, aggregate_id=%s) dead-lettered after %d attempts; last error: %s",
                attempt.event_id,
                attempt.kind,
                attempt.aggregate_id,
                EVENTS_MAX_ATTEMPTS_BEFORE_DEAD_LETTER,
                error,
            )
        else:
            _logger.warning(
                "Outbox event %d (aggregate_id=%s) failed attempt %d/%d, will retry: %s",
                attempt.event_id,
                attempt.aggregate_id,
                attempt.attempts,
                EVENTS_MAX_ATTEMPTS_BEFORE_DEAD_LETTER,
                error,
            )


async def claim_and_process_outbox_events(app: web.Application, engine: AsyncEngine) -> None:
    """Drain pending outbox events, one aggregate at a time, safe for concurrent replicas.

    When processing fails for an aggregate, its (kind, aggregate_id) is excluded from
    the rest of this drain so one poisoned aggregate cannot starve the healthy events
    behind it: the failure is marked on the row (attempt + backoff) and the drain
    moves on to the next aggregate. The drain aborts only after too many aggregates
    have failed with an infrastructure-like error (_INFRA_EXCEPTION_TYPES) and no
    success in between -- that pattern points at a broken DB/socketio connection
    rather than a handful of unrelated bad rows, and continuing would just spin.
    An application-level failure never counts towards this abort: the aggregate is
    still excluded from the rest of the drain, but healthy aggregates behind it keep
    draining no matter how many unrelated rows fail. Since excluded aggregates cannot
    be re-claimed within the drain, every counted failure concerns a distinct
    aggregate; a success resets the count. Everything left over is retried on the
    next wake-up or poll cycle, where the failed aggregates become claimable again
    (with their backoff applied).

    The drain also stops when every claimable event's aggregate is currently locked
    by another replica: the next cycle will retry, by which time that replica is likely done.

    Claim candidates come from a bounded batch (list_claimable_aggregates) that is
    refilled only once exhausted, so draining a backlog of N aggregates costs O(N)
    scans rather than one scan per claim. Stale candidates (claimed elsewhere or
    failed in this drain) are skipped from memory and cost only a cheap claim
    attempt, and the batch limit bounds how many of them can accumulate per refill.
    """
    failed_aggregates: set[ClaimableAggregate] = set()
    consecutive_infra_failed_aggregates = 0
    while True:
        async with pass_or_acquire_connection(engine) as conn:
            batch = await list_claimable_aggregates(conn, failed_aggregates)
        batch_was_claimable = False
        for candidate in batch:
            # (candidates already excluded from the scan by failed_aggregates)
            outcome = await _claim_and_process_aggregate(app, engine, candidate)
            if outcome is None:
                continue  # aggregate locked by another replica: move on to the next candidate
            batch_was_claimable = True
            if outcome.success:
                consecutive_infra_failed_aggregates = 0
                continue
            failed_aggregates.add(ClaimableAggregate(kind=outcome.kind, aggregate_id=outcome.aggregate_id))
            if not outcome.is_infra_error:
                continue  # application-level failure: does not threaten the rest of the drain
            consecutive_infra_failed_aggregates += 1
            if consecutive_infra_failed_aggregates >= _MAX_INFRA_FAILED_AGGREGATES_PER_DRAIN:
                _logger.warning(
                    "Stopping outbox drain after %d aggregates failed with an infrastructure-like"
                    " error and no success in-between; will retry on next cycle",
                    consecutive_infra_failed_aggregates,
                )
                return
        if not batch_was_claimable:
            # queue drained, or everything still pending is locked elsewhere:
            # rescanning now would just find the same batch again, so stop here
            return


async def purge_dead_letters(engine: AsyncEngine) -> None:
    """Remove dead-lettered events past the retention period (periodic maintenance).

    With several replicas the purge may run on all of them, which is harmless: the
    DELETE is idempotent and only removes rows every replica agrees are expired.
    """
    removed = await delete_expired_dead_letters(engine, _DEAD_LETTER_RETENTION)
    if removed:
        _logger.info(
            "Removed %d dead-lettered outbox event(s) older than %s",
            removed,
            _DEAD_LETTER_RETENTION,
        )
