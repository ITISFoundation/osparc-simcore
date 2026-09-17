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
are not transactional and may be re-sent (at-least-once, not exactly-once).

Each event records the comp_tasks columns that changed (`changed_columns`), so the
projection only pushes what actually changed, like the previous LISTEN/NOTIFY
payload did. All pending events of the same aggregate are coalesced into a single
projection (union of their changed_columns), so a burst of changes to one task
produces one socketio notification instead of one per event.
Failed attempts are counted on the row itself; events that exceed the maximum
number of attempts are dead-lettered (skipped by claims, kept for post-mortem).
"""

import dataclasses
import logging
from typing import Final

from aiohttp import web
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from models_library.projects_state import RunningState
from models_library.users import UserID
from simcore_postgres_database.utils_repos import transaction_context
from sqlalchemy.engine import Row
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
    MAX_ATTEMPTS,
    acquire_next_claimable_aggregate,
    build_claimable_predicate,
    delete_events,
    get_comp_task_row,
    get_project_owner,
    record_failed_attempts,
)
from ._utils import convert_state_from_db
from .models import ClaimOutcome

_MAX_FAILED_AGGREGATES_PER_DRAIN: Final[int] = 3

# only these count towards _MAX_FAILED_AGGREGATES_PER_DRAIN: a broken DB/socket
# connection affects every aggregate alike, unlike an application-level bug tied to
# specific rows, which must not halt the rest of an otherwise healthy drain
_INFRA_EXCEPTION_TYPES: Final[tuple[type[Exception], ...]] = (
    DBAPIError,
    OSError,
    TimeoutError,
)

# a change to any of these columns must refresh the node's outputs projection
_OUTPUTS_CHANGED_COLUMNS: Final[frozenset[str]] = frozenset({"outputs", "run_hash"})

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

    await notify_project_node_update(app, project, node_uuid)

    await notify_project_state_update(app, project)


async def process_outbox_event(
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
    comp_task_row = await get_comp_task_row(conn, task_id)

    if not comp_task_row:
        _logger.warning(
            "comp_tasks row (task_id=%d) not found; skipping stale outbox event",
            task_id,
        )
        return

    project_id = ProjectID(comp_task_row.project_id)
    node_id = NodeID(comp_task_row.node_id)

    try:
        project_owner = await get_project_owner(conn, project_id)
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


async def claim_and_process_one_outbox_event(
    app: web.Application,
    engine: AsyncEngine,
    exclude_aggregates: set[tuple[str, str]],
) -> ClaimOutcome | None:
    """Claim, process, and delete every pending event of one aggregate (at-least-once).

    Claiming never locks more than the aggregate it is about to process:
    _repository.acquire_next_claimable_aggregate elects (via the per-aggregate advisory
    lock) the oldest claimable aggregate no other replica holds; only then are event
    rows locked -- all pending events of the winning aggregate are co-claimed
    (FOR UPDATE SKIP LOCKED) and projected once: the union of their changed_columns
    describes everything that happened since the last projection, and
    process_outbox_event re-reads the current comp_tasks row, so a burst of N events
    for one aggregate fans out a single socketio notification instead of N.

    The claim-process-delete cycle runs in a single transaction: the advisory lock and
    the winner's row locks are held while the events are processed, and released
    automatically on commit or rollback. Rolling back a failed attempt undoes the
    *claim* (locks + pending delete) only: the projection writes through the app's
    repositories and socketio, outside this transaction, so retries are at-least-once
    and converge by re-reading the current row.

    ``exclude_aggregates`` is a set of (kind, aggregate_id) pairs the drain wants to
    skip, so an aggregate that already failed in this drain cannot starve the rest of
    the queue.

    Returns the ClaimOutcome (success flag + the aggregate claimed), or None when no
    event could be claimed -- either the queue is drained, or every candidate's
    aggregate is currently locked by another replica (retried on the next cycle).

    NOTE: processing runs while the transaction (and both locks) is open, so it must
    remain short-lived (DB updates + socketio notifications only).
    """
    processing_error: tuple[ClaimOutcome, list[int], Exception] | None = None

    try:
        async with transaction_context(engine) as conn:
            claimable = build_claimable_predicate(exclude_aggregates)

            # elect one free aggregate (advisory lock + row lock) before processing
            winner = await acquire_next_claimable_aggregate(conn, claimable)
            if winner is None:
                # drained, or every candidate aggregate is locked by another replica
                return None
            kind, aggregate_id, co_claimed_rows = winner
            claimed_ids = [r.id for r in co_claimed_rows]
            changed_columns = frozenset(col for r in co_claimed_rows for col in (r.changed_columns or []))

            _logger.debug(
                "Claimed %d outbox event(s) (kind=%s aggregate_id=%s)",
                len(claimed_ids),
                kind,
                aggregate_id,
            )
            outcome = ClaimOutcome(success=True, kind=kind, aggregate_id=aggregate_id)
            try:
                await process_outbox_event(app, conn, int(aggregate_id), changed_columns)
            except Exception as exc:
                # re-raise so the context manager rolls back the claim: the advisory
                # and row locks are released and the events stay in place for any
                # replica to re-claim. Only the claim is transactional -- a partially
                # applied projection already committed through the app's repositories
                # and socket.io and is NOT undone here (at-least-once: the retry
                # re-reads the current row, so the projection converges).
                processing_error = (outcome, claimed_ids, exc)
                raise

            # success: remove all co-claimed events within the same transaction
            await delete_events(conn, claimed_ids)
    except Exception:  # pylint: disable=broad-exception-caught
        if processing_error is None:
            raise

    if processing_error is not None:
        failed_outcome, claimed_ids, failed_exc = processing_error
        updated = await record_failed_attempts(engine, claimed_ids, failed_exc)
        _log_failed_attempts(updated, failed_exc)
        return dataclasses.replace(
            failed_outcome,
            success=False,
            is_infra_error=isinstance(failed_exc, _INFRA_EXCEPTION_TYPES),
        )
    return outcome


def _log_failed_attempts(updated_rows: list[Row], error: Exception) -> None:
    for row in updated_rows:
        if row.attempts >= MAX_ATTEMPTS:
            _logger.error(
                "Outbox event %d (kind=%s, aggregate_id=%s) dead-lettered after %d attempts; last error: %s",
                row.id,
                row.kind,
                row.aggregate_id,
                MAX_ATTEMPTS,
                error,
            )
        else:
            _logger.warning(
                "Outbox event %d (aggregate_id=%s) failed attempt %d/%d, will retry: %s",
                row.id,
                row.aggregate_id,
                row.attempts,
                MAX_ATTEMPTS,
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
    """
    failed_aggregates: set[tuple[str, str]] = set()
    consecutive_failed_aggregates = 0
    while True:
        outcome = await claim_and_process_one_outbox_event(app, engine, failed_aggregates)
        if outcome is None:
            return  # queue drained, or all remaining aggregates are locked elsewhere
        if outcome.success:
            consecutive_failed_aggregates = 0
            continue
        failed_aggregates.add((outcome.kind, outcome.aggregate_id))
        if not outcome.is_infra_error:
            continue  # application-level failure: does not threaten the rest of the drain
        consecutive_failed_aggregates += 1
        if consecutive_failed_aggregates >= _MAX_FAILED_AGGREGATES_PER_DRAIN:
            _logger.warning(
                "Stopping outbox drain after %d aggregates failed with an infrastructure-like"
                " error and no success in-between; will retry on next cycle",
                consecutive_failed_aggregates,
            )
            return
