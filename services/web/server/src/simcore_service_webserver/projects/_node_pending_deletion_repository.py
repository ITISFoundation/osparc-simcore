"""Repository for `nodes_pending_deletion` outbox.

A row is created at the start of a node deletion and removed only once the
storage cleanup has succeeded. If the storage step fails the row stays behind
so the periodic retry task can drive the cleanup to completion (see
`garbage_collector` package).

Mirror of `_pending_deletion_repository.py` for project-level deletions, but
keyed on `(project_uuid, node_id)`.
"""

from datetime import datetime
from typing import TypedDict

from aiohttp import web
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from models_library.users import UserID
from simcore_postgres_database.models.nodes_pending_deletion import (
    nodes_pending_deletion,
)
from simcore_postgres_database.utils_repos import (
    pass_or_acquire_connection,
    transaction_context,
)
from sqlalchemy import sql
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncConnection

from ..db.plugin import get_asyncpg_engine


class NodePendingDeletionRow(TypedDict):
    project_uuid: str
    node_id: str
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
    node_id: NodeID,
    requested_by: UserID,
) -> None:
    """Insert a pending-deletion row for `(project_uuid, node_id)`, or no-op if it already exists.

    Uses `ON CONFLICT DO NOTHING` to keep the original `requested_by` /
    `attempts` / `last_error` of an in-flight deletion intact when a user retries.
    """
    async with transaction_context(get_asyncpg_engine(app), connection) as conn:
        await conn.execute(
            pg_insert(nodes_pending_deletion)
            .values(
                project_uuid=f"{project_uuid}",
                node_id=f"{node_id}",
                requested_by=int(requested_by),
            )
            .on_conflict_do_nothing(
                index_elements=[
                    nodes_pending_deletion.c.project_uuid,
                    nodes_pending_deletion.c.node_id,
                ]
            )
        )


async def delete_pending_deletion(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    project_uuid: ProjectID,
    node_id: NodeID,
) -> None:
    """Remove the pending-deletion row for `(project_uuid, node_id)`. No-op if absent."""
    async with transaction_context(get_asyncpg_engine(app), connection) as conn:
        await conn.execute(
            nodes_pending_deletion.delete().where(
                (nodes_pending_deletion.c.project_uuid == f"{project_uuid}")
                & (nodes_pending_deletion.c.node_id == f"{node_id}")
            )
        )


async def record_failed_attempt(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    project_uuid: ProjectID,
    node_id: NodeID,
    error_message: str,
) -> None:
    """Bump `attempts`, set `last_attempt_at=now()` and store the error message."""
    async with transaction_context(get_asyncpg_engine(app), connection) as conn:
        await conn.execute(
            nodes_pending_deletion.update()
            .where(
                (nodes_pending_deletion.c.project_uuid == f"{project_uuid}")
                & (nodes_pending_deletion.c.node_id == f"{node_id}")
            )
            .values(
                attempts=nodes_pending_deletion.c.attempts + 1,
                last_attempt_at=sql.func.now(),
                last_error=error_message,
            )
        )


async def list_pending_deletions(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    limit: int = 100,
) -> list[NodePendingDeletionRow]:
    """Return outbox rows ordered by oldest `last_attempt_at` first (nulls first)."""
    async with pass_or_acquire_connection(get_asyncpg_engine(app), connection) as conn:
        result = await conn.stream(
            nodes_pending_deletion.select()
            .order_by(nodes_pending_deletion.c.last_attempt_at.asc().nulls_first())
            .limit(limit)
        )
        return [
            NodePendingDeletionRow(
                project_uuid=row.project_uuid,
                node_id=row.node_id,
                requested_by=row.requested_by,
                attempts=row.attempts,
                last_attempt_at=row.last_attempt_at,
                last_error=row.last_error,
                storage_task_uuid=row.storage_task_uuid,
            )
            async for row in result
        ]
