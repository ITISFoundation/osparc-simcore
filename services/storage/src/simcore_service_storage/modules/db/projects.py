from collections.abc import AsyncIterator
from contextlib import suppress

import sqlalchemy as sa
from models_library.projects import ProjectAtDB, ProjectID
from pydantic import ValidationError
from simcore_postgres_database.storage_models import projects
from sqlalchemy.ext.asyncio import AsyncConnection


async def list_valid_projects_in(
    conn: AsyncConnection,
    include_uuids: list[ProjectID],
) -> AsyncIterator[ProjectAtDB]:
    """

    NOTE that it lists ONLY validated projects in 'project_uuids'
    """
    async for row in await conn.stream(
        sa.select(projects).where(
            projects.c.uuid.in_(f"{pid}" for pid in include_uuids)
        )
    ):
        with suppress(ValidationError):
            yield ProjectAtDB.model_validate(row)


async def project_exists(
    conn: AsyncConnection,
    project_uuid: ProjectID,
) -> bool:
    return bool(
        await conn.scalar(
            sa.select(sa.func.count())
            .select_from(projects)
            .where(projects.c.uuid == f"{project_uuid}")
        )
        == 1
    )
