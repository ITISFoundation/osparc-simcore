"""Business logic of the db_listener domain: comp_tasks -> projects_nodes projection.

The comp_tasks DB trigger inserts into outbox_events on every meaningful change
(transactional outbox). This module claims, processes, and deletes those events in
short transactions, tolerating horizontal scaling (see "Claiming" below).

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

Claiming (why it is safe to run several web-server replicas):
a per-aggregate advisory lock (pg_try_advisory_xact_lock, keyed on kind +
aggregate_id) elects the replica that works on an aggregate, and its event rows are
locked (FOR UPDATE SKIP LOCKED) only after the aggregate was won. No two replicas
process events of the same aggregate concurrently, so socketio notifications of one
aggregate are never emitted out of order across replicas, while different aggregates
remain fully parallel. Including the kind in the lock key keeps this worker's lock
namespace separate from other (future) producers reusing the same id space. If the
events were claimed and deleted by another replica between the scan and the lock
being granted, the claim yields nothing and the drain moves on to the next candidate.

Candidate scan: one entry per *distinct* aggregate, oldest first, so a burst of events
on one aggregate locked elsewhere cannot crowd healthy aggregates out of the batch.
The drain reuses this bounded batch across claims and rescans only once it is
exhausted, keeping a backlog drain linear in the number of claimed aggregates.
Dead-lettered rows neither gate an aggregate nor affect its position in the queue.

Retry backoff: after attempt N an event is unclaimable until an exponentially growing
delay has elapsed. Without it, every unrelated outbox insert wakes the drain and a
transient outage could burn all attempts (dead-lettering everything) within seconds.
The backoff is gated per *aggregate*, not per row: with a per-row gate, a fresh event
would make the aggregate claimable while its older failed event is still backing off,
so the fresh projection would jump ahead of the older one (out-of-order notifications)
and each wake-up would burn another attempt on the stale event. Waiting for the oldest
backed-off event to mature keeps the events of an aggregate strictly ordered and lets
the whole backlog co-claim at once. Failures are recorded on the claim's own
connection, where the locks are still held, so no replica can re-claim the events
before their backoff is in place.

Infrastructure vs. application errors: a broken DB/socket connection affects every
aggregate alike, unlike a bug tied to specific rows, which must not halt the rest of
an otherwise healthy drain (see INFRA_EXCEPTION_TYPES).

Dead-letter purge: dead-lettered events are kept for post-mortem, but without a bound
they accumulate forever and the candidate scan still reads them on every drain.
Deleting them once older than the retention bounds that scan while keeping recent
failures investigable.
"""

import asyncio
import datetime
import logging
from enum import Enum, auto
from typing import Final

from aiohttp import web
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from models_library.projects_state import RunningState
from models_library.users import UserID
from simcore_postgres_database.utils_repos import pass_or_acquire_connection, transaction_context
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
    INFRA_EXCEPTION_TYPES,
    claim_aggregate,
    delete_expired_dead_letters,
    get_comp_task,
    get_project_owner,
    list_claimable_aggregates,
    record_failed_attempts,
    remove_claimed_events,
)
from ._utils import convert_state_from_db
from .errors import CompTaskNotFoundError
from .models import (
    DB_OUTBOX_CHANGED_COLUMN_STATE,
    DB_OUTBOX_CHANGED_COLUMNS_OUTPUTS,
    ClaimableAggregate,
    ClaimOutcome,
    FailedAttempt,
)

_MAX_INFRA_FAILED_AGGREGATES_PER_DRAIN: Final[int] = 3


class _BatchOutcome(Enum):
    """Outcome of processing one claimable batch inside the outbox drain."""

    ABORT_DRAIN = auto()  # infrastructure failures spiked: stop this drain
    DRAIN_EMPTY = auto()  # no aggregate in the batch was claimable: stop the drain
    MORE_TO_DRAIN = auto()  # at least one aggregate was claimed: refill and continue


_DEAD_LETTER_RETENTION: Final[datetime.timedelta] = datetime.timedelta(days=30)

# hard deadline on processing one aggregate: the socketio fan-out rides on RabbitMQ and
# a half-open broker connection can stall a publish indefinitely, which would pin the
# claim transaction, its locks, and pool connections until the replica restarts
_PROCESSING_TIMEOUT: Final[datetime.timedelta] = datetime.timedelta(seconds=30)

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

    claim_aggregate takes the per-aggregate advisory lock, then row-locks all
    pending events of that aggregate (FOR UPDATE SKIP LOCKED). Their changed_columns
    are unioned and the current comp_tasks row is re-read, so a burst of N events
    produces a single socketio notification.

    The cycle is one transaction. The locks are held while processing and released
    on commit; a failed projection is recorded on the events (attempt + backoff) in
    the same transaction, so no other replica can re-claim them before the backoff
    is in place. The projection writes through the app's repositories and socket.io
    outside this transaction, so a retried attempt converges by re-reading the
    current row.

    Returns None when another replica holds the aggregate or its pending events are
    gone. Processing runs with the locks open, so it is capped by
    _PROCESSING_TIMEOUT: a stalled publish aborts the claim as an infrastructure
    failure instead of pinning the locks.
    """
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
            # the savepoint keeps the claim transaction usable if a read inside it fails
            async with conn.begin_nested(), asyncio.timeout(_PROCESSING_TIMEOUT.total_seconds()):
                await _process_outbox_event(app, conn, int(claimed.aggregate_id), claimed.changed_columns)
        except Exception as exc:  # pylint: disable=broad-exception-caught
            updated = await record_failed_attempts(conn, claimed, exc)
            _log_failed_attempts(updated, exc)
            return ClaimOutcome(
                success=False,
                kind=claimed.kind,
                aggregate_id=claimed.aggregate_id,
                is_infra_error=isinstance(exc, INFRA_EXCEPTION_TYPES),
            )

        await remove_claimed_events(conn, claimed.event_ids)
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


async def _process_claimable_batch(
    app: web.Application,
    engine: AsyncEngine,
    batch: list[ClaimableAggregate],
    failed_aggregates: set[ClaimableAggregate],
    consecutive_infra_failed_aggregates: int,
) -> tuple[int, _BatchOutcome]:
    """Claim and process every candidate of one batch, updating the drain state in place.

    ``failed_aggregates`` is mutated with each failed (kind, aggregate_id) so the next
    batch excludes them. Returns the updated consecutive infrastructure-failure count
    and the outcome deciding whether the caller keeps draining (see _BatchOutcome).
    """
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
            return consecutive_infra_failed_aggregates, _BatchOutcome.ABORT_DRAIN
    if not batch_was_claimable:
        # queue drained, or everything still pending is locked elsewhere:
        # rescanning now would just find the same batch again, so stop here
        return consecutive_infra_failed_aggregates, _BatchOutcome.DRAIN_EMPTY
    return consecutive_infra_failed_aggregates, _BatchOutcome.MORE_TO_DRAIN


async def claim_and_process_outbox_events(app: web.Application, engine: AsyncEngine) -> None:
    """Drain pending outbox events, one aggregate at a time, safe for concurrent replicas.

    On failure the events are marked (attempt + backoff) and the aggregate is
    excluded from the rest of this drain, so one poisoned aggregate cannot starve
    the healthy events behind it. It becomes claimable again on a later cycle, once
    its backoff has passed. The drain aborts only when
    _MAX_INFRA_FAILED_AGGREGATES_PER_DRAIN distinct aggregates fail with an
    infrastructure-like error (INFRA_EXCEPTION_TYPES) with no success in between:
    that pattern points at a broken DB/socketio connection, and continuing would
    just spin. Application-level failures never count towards that limit.

    The drain also stops when nothing is left to claim here: either the queue is
    empty or every pending aggregate is locked by another replica, which the next
    cycle retries.

    Candidates come from a bounded batch refilled only when exhausted, so a backlog
    of N aggregates costs O(N) scans rather than one scan per claim.
    """
    failed_aggregates: set[ClaimableAggregate] = set()
    consecutive_infra_failed_aggregates = 0
    while True:
        async with pass_or_acquire_connection(engine) as conn:
            batch = await list_claimable_aggregates(conn, failed_aggregates)
        consecutive_infra_failed_aggregates, outcome = await _process_claimable_batch(
            app, engine, batch, failed_aggregates, consecutive_infra_failed_aggregates
        )
        if outcome in (_BatchOutcome.ABORT_DRAIN, _BatchOutcome.DRAIN_EMPTY):
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
