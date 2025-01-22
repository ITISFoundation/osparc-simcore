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


async def get_trashed_by_primary_gid_from_project(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    projects_uuids: list[ProjectID],
) -> list[GroupID | None]:
    """
    Returns trashed_by as GroupID instead of UserID as is in the database
    """
    async with pass_or_acquire_connection(get_asyncpg_engine(app), connection) as conn:
        query = (
            sa.select(
                users.c.primary_gid.label("trashed_by_primary_gid"),
            )
            .select_from(projects.outerjoin(users, projects.c.trashed_by == users.c.id))
            .where(projects.c.uuid.in_(projects_uuids))
        ).order_by(
            # Preserves the order of projects_uuids
            sa.case(
                *[
                    (projects.c.uuid == uuid, index)
                    for index, uuid in enumerate(projects_uuids)
                ]
            )
        )
        result = await conn.stream(query)
        return [row.trashed_by_primary_gid async for row in result]
