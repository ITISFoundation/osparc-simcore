import logging

import sqlalchemy as sa
from aiohttp import web
from models_library.groups import GroupID
from models_library.projects import ProjectID
from simcore_postgres_database.models.projects import projects
from simcore_postgres_database.models.users import users
from simcore_postgres_database.utils_repos import (
    get_columns_from_db_model,
    pass_or_acquire_connection,
    transaction_context,
)
from sqlalchemy.ext.asyncio import AsyncConnection

from ..db.plugin import get_asyncpg_engine
from .exceptions import ProjectNotFoundError
from .models import ProjectDB

_logger = logging.getLogger(__name__)


PROJECT_DB_COLS = get_columns_from_db_model(  # noqa: RUF012
    # NOTE: MD: I intentionally didn't include the workbench. There is a special interface
    # for the workbench, and at some point, this column should be removed from the table.
    # The same holds true for access_rights/ui/classifiers/quality, but we have decided to proceed step by step.
    projects,
    ProjectDB,
)


async def patch_project(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    project_uuid: ProjectID,
    new_partial_project_data: dict,
) -> ProjectDB:

    async with transaction_context(get_asyncpg_engine(app), connection) as conn:
        result = await conn.stream(
            projects.update()
            .values(last_change_date=sa.func.now(), **new_partial_project_data)
            .where(projects.c.uuid == f"{project_uuid}")
            .returning(*PROJECT_DB_COLS)
        )
        row = await result.first()
        if row is None:
            raise ProjectNotFoundError(project_uuid=project_uuid)
        return ProjectDB.model_validate(row)


def _select_trashed_by_primary_gid_query():
    return sa.select(
        users.c.primary_gid.label("trashed_by_primary_gid"),
    ).select_from(projects.outerjoin(users, projects.c.trashed_by == users.c.id))


async def get_trashed_by_primary_gid(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    projects_uuid: ProjectID,
) -> GroupID | None:
    query = _select_trashed_by_primary_gid_query().where(
        projects.c.uuid == projects_uuid
    )

    async with pass_or_acquire_connection(get_asyncpg_engine(app), connection) as conn:
        result = await conn.execute(query)
        row = result.first()
        return row.trashed_by_primary_gid if row else None


async def batch_get_trashed_by_primary_gid(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    projects_uuids: list[ProjectID],
) -> list[GroupID | None]:
    """Batch version of get_trashed_by_primary_gid

    Returns:
        values of trashed_by_primary_gid in the SAME ORDER as projects_uuids
    """
    if not projects_uuids:
        return []

    projects_uuids_str = [f"{uuid}" for uuid in projects_uuids]

    query = (
        _select_trashed_by_primary_gid_query().where(
            projects.c.uuid.in_(projects_uuids_str)
        )
    ).order_by(
        # Preserves the order of folders_ids
        # SEE https://docs.sqlalchemy.org/en/20/core/sqlelement.html#sqlalchemy.sql.expression.case
        sa.case(
            {
                project_uuid: index
                for index, project_uuid in enumerate(projects_uuids_str)
            },
            value=projects.c.uuid,
        )
    )
    async with pass_or_acquire_connection(get_asyncpg_engine(app), connection) as conn:
        result = await conn.stream(query)
        return [row.trashed_by_primary_gid async for row in result]
