"""Repository for `projects_pending_deletion` outbox.

A row is created at the start of a project deletion and removed only once the
storage cleanup AND the `projects` row removal have both succeeded. If any step
fails the row stays behind so the periodic retry task can drive the cleanup to
completion (see `garbage_collector` package).
"""

from datetime import datetime
from typing import TypedDict

from aiohttp import web
from models_library.projects import ProjectID
from models_library.users import UserID
from simcore_postgres_database.models.projects_pending_deletion import (
    projects_pending_deletion,
)
from simcore_postgres_database.utils_repos import (
    pass_or_acquire_connection,
    transaction_context,
)
from sqlalchemy import sql
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncConnection

from ..db.plugin import get_asyncpg_engine


class PendingDeletionRow(TypedDict):
    project_uuid: str
    requested_by: int | None
    attempts: int
    last_attempt_at: datetime | None
    last_error: str | None
    storage_task_uuid: str | None


async def upsert_pending_deletion(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    project_uuid: ProjectID,
    requested_by: UserID,
) -> None:
    """Insert a pending-deletion row for `project_uuid`, or no-op if it already exists.

    Uses an `ON CONFLICT DO NOTHING` to keep the original `requested_by` /
    `attempts` / `last_error` of an in-flight deletion intact when a user retries.
    """
    async with transaction_context(get_asyncpg_engine(app), connection) as conn:
        await conn.execute(
            pg_insert(projects_pending_deletion)
            .values(
                project_uuid=f"{project_uuid}",
                requested_by=int(requested_by),
            )
            .on_conflict_do_nothing(index_elements=[projects_pending_deletion.c.project_uuid])
        )


async def delete_pending_deletion(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    project_uuid: ProjectID,
) -> None:
    """Remove the pending-deletion row for `project_uuid`. No-op if absent."""
    async with transaction_context(get_asyncpg_engine(app), connection) as conn:
        await conn.execute(
            projects_pending_deletion.delete().where(projects_pending_deletion.c.project_uuid == f"{project_uuid}")
        )


async def record_failed_attempt(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    project_uuid: ProjectID,
    error_message: str,
) -> None:
    """Bump `attempts`, set `last_attempt_at=now()` and store the error message."""
    async with transaction_context(get_asyncpg_engine(app), connection) as conn:
        await conn.execute(
            projects_pending_deletion.update()
            .where(projects_pending_deletion.c.project_uuid == f"{project_uuid}")
            .values(
                attempts=projects_pending_deletion.c.attempts + 1,
                last_attempt_at=sql.func.now(),
                last_error=error_message,
            )
        )


async def list_pending_deletions(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    limit: int = 100,
) -> list[PendingDeletionRow]:
    """Return outbox rows ordered by oldest `last_attempt_at` first (nulls first)."""
    async with pass_or_acquire_connection(get_asyncpg_engine(app), connection) as conn:
        result = await conn.stream(
            projects_pending_deletion.select()
            .order_by(projects_pending_deletion.c.last_attempt_at.asc().nulls_first())
            .limit(limit)
        )
        return [
            PendingDeletionRow(
                project_uuid=row.project_uuid,
                requested_by=row.requested_by,
                attempts=row.attempts,
                last_attempt_at=row.last_attempt_at,
                last_error=row.last_error,
                storage_task_uuid=row.storage_task_uuid,
            )
            async for row in result
        ]
