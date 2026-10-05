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

import datetime as dt
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
from sqlalchemy.exc import DBAPIError
from sqlalchemy.exc import DisconnectionError as SQLAlchemyDisconnectionError
from sqlalchemy.exc import TimeoutError as SQLAlchemyTimeoutError
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine
from sqlalchemy.sql import func, select, tuple_

from ..projects import exceptions
from .errors import CompTaskNotFoundError
from .models import (
    AggregateID,
    AggregateType,
    ClaimableAggregate,
    ClaimedAggregate,
    CompTask,
    FailedAttempt,
    OutboxEventID,
)

EVENTS_MAX_ATTEMPTS_BEFORE_DEAD_LETTER: Final[int] = 10
MAX_CONSIDERED_AGGREGATES_PER_CLAIM_ATTEMPT: Final[int] = 10
MAX_CO_CLAIMED_EVENTS_PER_AGGREGATE: Final[int] = 100
LAST_ERROR_MAX_LEN: Final[int] = 500

# exponential retry backoff: after attempt N an event is unclaimable for
# min(RETRY_BACKOFF_BASE_S * 2**N, RETRY_BACKOFF_MAX_S) seconds. Without this gate,
# every unrelated outbox insert wakes the drain and a transient outage could burn all
# attempts (and dead-letter everything) within seconds of wake-up storms.
RETRY_BACKOFF_BASE_S: Final[int] = 2
RETRY_BACKOFF_MAX_S: Final[int] = 900

# Exceptions that signal an infrastructure outage rather than an application-level bug:
# a broken DB/socket connection affects every aggregate alike, unlike a bug tied to
# specific rows, which must not halt the rest of an otherwise healthy drain.
# NOTE: sqlalchemy.exc.TimeoutError (pool checkout starvation) subclasses neither the
# builtin TimeoutError nor DBAPIError, and DisconnectionError (e.g. ConnectionLostError
# after a server restart) subclasses neither either -- both must be listed explicitly
# or a database-wide outage is misclassified as application-level.
INFRA_EXCEPTION_TYPES: Final[tuple[type[Exception], ...]] = (
    DBAPIError,
    SQLAlchemyDisconnectionError,
    SQLAlchemyTimeoutError,
    OSError,
    TimeoutError,
)


def _scanned_events_predicate(exclude_aggregates: set[ClaimableAggregate]) -> ColumnElement[bool]:
    """Rows considered when scanning for candidate aggregates: own kind, and not an
    aggregate the current drain already failed on.

    The attempts/backoff gates are deliberately NOT here: they are applied per
    *aggregate* in list_claimable_aggregates (see why there).
    """
    scanned = outbox_events.c.kind == DB_OUTBOX_KIND_COMP_TASK_SYNC
    if exclude_aggregates:
        scanned = scanned & ~tuple_(outbox_events.c.kind, outbox_events.c.aggregate_id).in_(
            [(a.kind, a.aggregate_id) for a in exclude_aggregates]
        )
    return scanned


async def list_claimable_aggregates(
    conn: AsyncConnection, exclude_aggregates: set[ClaimableAggregate]
) -> list[ClaimableAggregate]:
    """List the oldest claimable aggregates (read-only: no locking at all).

    One row per *distinct* aggregate (GROUP BY), oldest aggregate first, so a burst
    of events on one aggregate locked elsewhere cannot crowd healthy aggregates out
    of the batch. The drain reuses this bounded batch across claims and only pays
    the scan cost again once the batch is exhausted, which keeps draining a backlog
    linear in the number of claimed aggregates.

    The retry backoff is gate-checked per *aggregate*, not per row: an aggregate is a
    candidate only when none of its events is still backing off (bool_and: every row
    is either exhausted or due). With a per-row gate, one fresh event would make the
    aggregate instantly claimable while its older failed event is still in backoff,
    so the fresh event's projection would jump ahead of the older one (out-of-order
    notifications for the same task) and each wake-up would burn another attempt on
    the stale event. Waiting for the oldest backed-off event to mature keeps events of
    one aggregate strictly ordered and lets the whole backlog co-claim at once.

    ORDER BY uses min(...) FILTER (attempts < MAX) so dead-lettered (exhausted) rows
    neither gate the aggregate nor pull its position in the queue.
    """
    retryable = outbox_events.c.attempts < EVENTS_MAX_ATTEMPTS_BEFORE_DEAD_LETTER
    exhausted_or_due = (outbox_events.c.attempts >= EVENTS_MAX_ATTEMPTS_BEFORE_DEAD_LETTER) | (
        outbox_events.c.next_attempt_at <= func.now()
    )
    oldest_retryable = func.min(outbox_events.c.modified).filter(retryable)
    candidate_rows = (
        await conn.execute(
            select(outbox_events.c.kind, outbox_events.c.aggregate_id)
            .where(_scanned_events_predicate(exclude_aggregates))
            .group_by(outbox_events.c.kind, outbox_events.c.aggregate_id)
            # every non-exhausted event must be due (no row still backing off), and at
            # least one retryable event must exist (else the aggregate is dead-lettered)
            .having(func.bool_and(exhausted_or_due) & func.bool_or(retryable))
            .order_by(oldest_retryable, func.min(outbox_events.c.id).filter(retryable))
            .limit(MAX_CONSIDERED_AGGREGATES_PER_CLAIM_ATTEMPT)
        )
    ).fetchall()
    return [ClaimableAggregate(kind=r.kind, aggregate_id=r.aggregate_id) for r in candidate_rows]


async def claim_aggregate(conn: AsyncConnection, candidate: ClaimableAggregate) -> ClaimedAggregate | None:
    """Advisory-lock and row-lock a known aggregate, co-claiming its pending events.

    The per-aggregate advisory lock (pg_try_advisory_xact_lock, keyed on kind +
    aggregate_id) is taken first: an aggregate already processed by another replica
    is skipped and stays fully parallel to it. Including kind in the lock key keeps
    this worker's lock namespace separate from other (future) producers that may
    reuse the same id space.

    Once the lock is won, the events are re-checked with FOR UPDATE SKIP LOCKED: if
    they were claimed and deleted by another replica between the read-only scan and
    the lock being granted, this returns None (the harmless advisory lock is kept
    until commit) and the caller moves on to the next candidate.

    Holding the row lock until commit guarantees events of the same aggregate are
    never processed concurrently, so socketio notifications for one aggregate can't
    be emitted out of order across replicas.

    Returns the ClaimedAggregate (the locked event ids plus the union of their
    changed_columns), or None when the aggregate is locked elsewhere or has no
    claimable event left.
    """
    lock_key = f"{candidate.kind}:{candidate.aggregate_id}"
    acquired = (
        await conn.execute(select(func.pg_try_advisory_xact_lock(func.hashtextextended(lock_key, 0))))
    ).scalar_one()
    if not acquired:
        return None

    co_claimed_rows = (
        await conn.execute(
            select(outbox_events.c.id, outbox_events.c.changed_columns)
            .where(
                outbox_events.c.kind == candidate.kind,
                outbox_events.c.aggregate_id == candidate.aggregate_id,
                outbox_events.c.attempts < EVENTS_MAX_ATTEMPTS_BEFORE_DEAD_LETTER,
                outbox_events.c.next_attempt_at <= func.now(),
            )
            .order_by(outbox_events.c.modified, outbox_events.c.id)
            .limit(MAX_CO_CLAIMED_EVENTS_PER_AGGREGATE)
            .with_for_update(skip_locked=True)
        )
    ).fetchall()
    if not co_claimed_rows:
        return None
    return ClaimedAggregate(
        kind=candidate.kind,
        aggregate_id=candidate.aggregate_id,
        event_ids=[OutboxEventID(r.id) for r in co_claimed_rows],
        changed_columns=frozenset(col for r in co_claimed_rows for col in (r.changed_columns or [])),
    )


async def remove_claimed_events(conn: AsyncConnection, event_ids: Sequence[OutboxEventID]) -> None:
    await conn.execute(outbox_events.delete().where(outbox_events.c.id.in_(event_ids)))


async def record_failed_attempts(
    engine: AsyncEngine, claimed: ClaimedAggregate, error: Exception
) -> list[FailedAttempt]:
    """Record a failed processing attempt on every co-claimed event (separate transaction).

    The UPDATE bumps `attempts`/`last_error`, pushes `next_attempt_at` forward with an
    exponential backoff (the event stays unclaimable until then), and (via the
    auto-update trigger) refreshes `modified`, which moves the events to the back of
    the oldest-first queue.
    Returns the updated events so the caller can report retries vs. dead-lettering.

    This transaction first takes the *blocking* per-aggregate advisory lock (same key as
    claim_aggregate): the claim transaction that failed already released its locks when
    it rolled back, so without this lock a stale candidate scanned before the failure
    could re-claim the very same events and bump their attempts again before the backoff
    was even recorded (burning retries with no wait). Claims use pg_try_advisory_xact_lock
    on the same key, so they never deadlock against this one -- they simply return None
    and move on to their next candidate while the bookkeeping finishes.
    """
    backoff_secs = func.least(
        RETRY_BACKOFF_BASE_S * func.pow(2, outbox_events.c.attempts + 1),
        RETRY_BACKOFF_MAX_S,
    )
    lock_key = f"{claimed.kind}:{claimed.aggregate_id}"
    async with transaction_context(engine) as conn:
        # wait for the aggregate lock any concurrent claim would have taken (see docstring)
        await conn.execute(select(func.pg_advisory_xact_lock(func.hashtextextended(lock_key, 0))))
        result = await conn.execute(
            outbox_events.update()
            .values(
                attempts=outbox_events.c.attempts + 1,
                last_error=str(error)[:LAST_ERROR_MAX_LEN],
                next_attempt_at=func.now() + func.make_interval(0, 0, 0, 0, 0, 0, backoff_secs),
            )
            .where(outbox_events.c.id.in_(claimed.event_ids))
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


async def delete_expired_dead_letters(engine: AsyncEngine, retention: dt.timedelta) -> int:
    """Delete dead-lettered events older than the retention period, returning the number of rows removed.

    Dead-lettered events (attempts exhausted) are kept for post-mortem, but without a
    bound they accumulate forever: claims skip them via the attempts filter, yet the
    candidate scan still reads them on every drain. Deleting them once they are older
    than ``retention`` bounds that scan while keeping recent failures investigable.
    """
    async with transaction_context(engine) as conn:
        result = await conn.execute(
            outbox_events.delete().where(
                outbox_events.c.kind == DB_OUTBOX_KIND_COMP_TASK_SYNC,
                outbox_events.c.attempts >= EVENTS_MAX_ATTEMPTS_BEFORE_DEAD_LETTER,
                outbox_events.c.modified < dt.datetime.now(dt.UTC) - retention,
            )
        )
        return result.rowcount if result.rowcount is not None else 0


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
