"""Data access of the db_listener domain (outbox_events, comp_tasks, projects)."""

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
    ClaimableAggregate,
    ClaimedAggregate,
    CompTask,
    EventKind,
    FailedAttempt,
    OutboxEventID,
)

EVENTS_MAX_ATTEMPTS_BEFORE_DEAD_LETTER: Final[int] = 10
MAX_CONSIDERED_AGGREGATES_PER_CLAIM_ATTEMPT: Final[int] = 10
MAX_CO_CLAIMED_EVENTS_PER_AGGREGATE: Final[int] = 100
LAST_ERROR_MAX_LEN: Final[int] = 500

RETRY_BACKOFF_BASE_S: Final[int] = 2
RETRY_BACKOFF_MAX_S: Final[int] = 900

# NOTE: sqlalchemy's TimeoutError and DisconnectionError subclass neither the builtin
# TimeoutError nor DBAPIError, so they must be listed explicitly.
INFRA_EXCEPTION_TYPES: Final[tuple[type[Exception], ...]] = (
    DBAPIError,
    SQLAlchemyDisconnectionError,
    SQLAlchemyTimeoutError,
    OSError,
    TimeoutError,
)


def _scanned_events_predicate(exclude_aggregates: set[ClaimableAggregate]) -> ColumnElement[bool]:
    """Rows scanned for candidate aggregates: own kind, minus the excluded aggregates."""
    scanned = outbox_events.c.kind == DB_OUTBOX_KIND_COMP_TASK_SYNC
    if exclude_aggregates:
        scanned = scanned & ~tuple_(outbox_events.c.kind, outbox_events.c.aggregate_id).in_(
            [(a.kind, a.aggregate_id) for a in exclude_aggregates]
        )
    return scanned


async def list_claimable_aggregates(
    conn: AsyncConnection, exclude_aggregates: set[ClaimableAggregate]
) -> list[ClaimableAggregate]:
    """List up to MAX_CONSIDERED_AGGREGATES_PER_CLAIM_ATTEMPT distinct aggregates, oldest first (no locking).

    An aggregate is listed only if none of its events is still backing off and at
    least one is retryable (attempts below the maximum).
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
    """Take the transaction-scoped advisory lock of the aggregate, then row-lock its due events.

    Returns the locked event ids with the union of their changed_columns, or None when
    the advisory lock is held elsewhere or no claimable event is left.
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
    conn: AsyncConnection, claimed: ClaimedAggregate, error: Exception
) -> list[FailedAttempt]:
    """Bump `attempts`, set `last_error` and push `next_attempt_at` (exponential backoff) on the claimed events."""
    backoff_secs = func.least(
        RETRY_BACKOFF_BASE_S * func.pow(2, outbox_events.c.attempts + 1),
        RETRY_BACKOFF_MAX_S,
    )
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
            kind=EventKind(r.kind),
            aggregate_id=AggregateID(r.aggregate_id),
            attempts=r.attempts,
        )
        for r in result.fetchall()
    ]


async def delete_expired_dead_letters(engine: AsyncEngine, retention: dt.timedelta) -> int:
    """Delete events with exhausted attempts not modified within ``retention``; returns the rows removed."""
    async with transaction_context(engine) as conn:
        result = await conn.execute(
            outbox_events.delete().where(
                outbox_events.c.kind == DB_OUTBOX_KIND_COMP_TASK_SYNC,
                outbox_events.c.attempts >= EVENTS_MAX_ATTEMPTS_BEFORE_DEAD_LETTER,
                outbox_events.c.modified < func.now() - retention,
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
