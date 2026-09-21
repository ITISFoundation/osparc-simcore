"""Data access of the db_listener domain (outbox_events, comp_tasks, projects).

Pure persistence I/O for the transactional outbox that the comp_tasks DB trigger
feeds: claiming, deleting, and failure-recording on `outbox_events`, plus the
read-only lookups the projection needs. No business logic here -- orchestration
lives in `_service.py`.

Claiming mechanics (why it is safe to run several web-server replicas):
a per-aggregate advisory lock (pg_try_advisory_xact_lock, keyed on
kind + aggregate_id) elects the replica that works on an aggregate, and event
rows are locked (FOR UPDATE SKIP LOCKED) only after the aggregate was selected.
No two replicas can ever process events for the same aggregate concurrently,
while different aggregates remain fully parallel.
"""

from collections.abc import Sequence
from typing import Final

from models_library.projects import ProjectID
from models_library.users import UserID
from pydantic.types import PositiveInt
from simcore_postgres_database.models.comp_tasks import comp_tasks
from simcore_postgres_database.models.outbox_events import outbox_events
from simcore_postgres_database.utils_repos import transaction_context
from simcore_postgres_database.webserver_models import (
    DB_OUTBOX_KIND_COMP_TASK_SYNC,
    projects,
)
from sqlalchemy import ColumnElement
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine
from sqlalchemy.sql import func, select, tuple_

from ..projects import exceptions
from .errors import CompTaskNotFoundError
from .models import (
    AggregateID,
    AggregateType,
    ClaimedAggregate,
    CompTask,
    FailedAttempt,
    OutboxEventID,
)

EVENTS_MAX_ATTEMPTS_BEFORE_DEAD_LETTER: Final[int] = 10
MAX_CONSIDERED_AGGREGATES_PER_CLAIM_ATTEMPT: Final[int] = 10
MAX_CO_CLAIMED_EVENTS_PER_AGGREGATE: Final[int] = 100
LAST_ERROR_MAX_LEN: Final[int] = 500


def _claimable_events_predicate(exclude_aggregates: set[tuple[AggregateType, AggregateID]]) -> ColumnElement[bool]:
    """Predicate selecting events this worker may claim: own kind, not exhausted,
    and not an aggregate the current drain already failed on."""
    claimable = (outbox_events.c.kind == DB_OUTBOX_KIND_COMP_TASK_SYNC) & (
        outbox_events.c.attempts < EVENTS_MAX_ATTEMPTS_BEFORE_DEAD_LETTER
    )
    if exclude_aggregates:
        claimable = claimable & ~tuple_(outbox_events.c.kind, outbox_events.c.aggregate_id).in_(
            list(exclude_aggregates)
        )
    return claimable


async def acquire_next_claimable_aggregate(
    conn: AsyncConnection, exclude_aggregates: set[tuple[AggregateType, AggregateID]]
) -> ClaimedAggregate | None:
    """Pick, advisory-lock, and row-lock the oldest claimable aggregate no other replica holds.

    The oldest distinct aggregates are listed with a read-only query (no locking at
    all), so candidate selection can never block or strand another replica. Their
    aggregates are then offered the per-aggregate advisory lock
    (pg_try_advisory_xact_lock, keyed on kind + aggregate_id) one at a time: an
    aggregate already processed by another replica is skipped and stays fully
    parallel to it. Including kind in the lock key keeps this worker's lock
    namespace separate from other (future) producers that may reuse the same id space.

    Once a lock is won, its rows are re-checked with FOR UPDATE SKIP LOCKED: if they
    were claimed and deleted by another replica between the read-only scan above and
    the lock being granted, that candidate is skipped (the harmless advisory lock is
    kept until commit) and the next one is tried -- so a single raced-away candidate
    can never end candidate selection early while others in the same batch are still
    free. Holding the row lock until commit guarantees events of the same aggregate
    are never processed concurrently, so socketio notifications for one aggregate
    can't be emitted out of order across replicas.

    Returns the ClaimedAggregate (the locked event ids plus the union of their
    changed_columns), or None when no candidate aggregate is both free and still
    pending.
    """
    claimable = _claimable_events_predicate(exclude_aggregates)

    # one row per aggregate (GROUP BY), oldest aggregate first: the batch limit then
    # covers MAX_CONSIDERED_AGGREGATES_PER_CLAIM_ATTEMPT *distinct* aggregates, so a
    # burst of events on one aggregate locked elsewhere cannot crowd healthy
    # aggregates out of the batch
    candidate_rows = (
        await conn.execute(
            select(outbox_events.c.kind, outbox_events.c.aggregate_id)
            .where(claimable)
            .group_by(outbox_events.c.kind, outbox_events.c.aggregate_id)
            .order_by(func.min(outbox_events.c.modified), func.min(outbox_events.c.id))
            .limit(MAX_CONSIDERED_AGGREGATES_PER_CLAIM_ATTEMPT)
        )
    ).all()

    for kind, aggregate_id in candidate_rows:
        # lock namespace must match the claim namespace (kind + aggregate_id):
        # another producer reusing the same id space must not collide with ours
        acquired = (
            await conn.execute(
                select(func.pg_try_advisory_xact_lock(func.hashtextextended(f"{kind}:{aggregate_id}", 0)))
            )
        ).scalar_one()
        if not acquired:
            continue

        co_claimed_rows = (
            await conn.execute(
                select(outbox_events.c.id, outbox_events.c.changed_columns)
                .where(
                    outbox_events.c.kind == kind,
                    outbox_events.c.aggregate_id == aggregate_id,
                    outbox_events.c.attempts < EVENTS_MAX_ATTEMPTS_BEFORE_DEAD_LETTER,
                )
                .order_by(outbox_events.c.modified, outbox_events.c.id)
                .limit(MAX_CO_CLAIMED_EVENTS_PER_AGGREGATE)
                .with_for_update(skip_locked=True)
            )
        ).fetchall()
        if co_claimed_rows:
            return ClaimedAggregate(
                kind=AggregateType(kind),
                aggregate_id=AggregateID(aggregate_id),
                event_ids=[OutboxEventID(r.id) for r in co_claimed_rows],
                changed_columns=frozenset(col for r in co_claimed_rows for col in (r.changed_columns or [])),
            )
        # raced away since the read-only scan above: try the next candidate instead
        # of giving up on the whole batch
    return None


async def remove_claimed_events(conn: AsyncConnection, event_ids: Sequence[OutboxEventID]) -> None:
    await conn.execute(outbox_events.delete().where(outbox_events.c.id.in_(event_ids)))


async def record_failed_attempts(
    engine: AsyncEngine, event_ids: Sequence[OutboxEventID], error: Exception
) -> list[FailedAttempt]:
    """Record a failed processing attempt on every co-claimed event (separate transaction).

    The UPDATE bumps `attempts`/`last_error` and (via the auto-update trigger)
    refreshes `modified`, which pushes the events to the back of the oldest-first
    queue and thereby spaces out retries.
    Returns the updated events so the caller can report retries vs. dead-lettering.
    """
    async with transaction_context(engine) as conn:
        result = await conn.execute(
            outbox_events.update()
            .values(
                attempts=outbox_events.c.attempts + 1,
                last_error=str(error)[:LAST_ERROR_MAX_LEN],
            )
            .where(outbox_events.c.id.in_(event_ids))
            .returning(
                outbox_events.c.id,
                outbox_events.c.kind,
                outbox_events.c.aggregate_id,
                outbox_events.c.attempts,
            )
        )
        return [
            FailedAttempt(
                event_id=OutboxEventID(r.id),
                kind=AggregateType(r.kind),
                aggregate_id=AggregateID(r.aggregate_id),
                attempts=r.attempts,
            )
            for r in result.fetchall()
        ]


async def get_comp_task(conn: AsyncConnection, task_id: int) -> CompTask:
    result = await conn.execute(
        select(
            comp_tasks.c.task_id,
            comp_tasks.c.project_id,
            comp_tasks.c.node_id,
            comp_tasks.c.outputs,
            comp_tasks.c.run_hash,
            comp_tasks.c.state,
        ).where(comp_tasks.c.task_id == task_id)
    )
    row = result.fetchone()
    if row is None:
        raise CompTaskNotFoundError(task_id=task_id)
    return CompTask(
        task_id=row.task_id,
        project_id=row.project_id,
        node_id=row.node_id,
        outputs=row.outputs,
        run_hash=row.run_hash,
        state=row.state,
    )


async def get_project_owner(conn: AsyncConnection, project_uuid: ProjectID) -> UserID:
    the_project_owner: PositiveInt | None = (
        await conn.execute(select(projects.c.prj_owner).where(projects.c.uuid == f"{project_uuid}"))
    ).scalar_one_or_none()
    if not the_project_owner:
        raise exceptions.ProjectOwnerNotFoundError(project_uuid=project_uuid)
    return UserID(the_project_owner)
