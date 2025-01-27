from collections.abc import AsyncIterator
from contextlib import suppress

import sqlalchemy as sa
from aiopg.sa.connection import SAConnection
from models_library.projects import ProjectAtDB, ProjectID
from pydantic import ValidationError
from simcore_postgres_database.storage_models import projects


async def list_valid_projects_in(
    conn: SAConnection,
    include_uuids: list[ProjectID],
) -> AsyncIterator[ProjectAtDB]:
    """

    NOTE that it lists ONLY validated projects in 'project_uuids'
    """
    async for row in conn.execute(
        sa.select(projects).where(
            projects.c.uuid.in_(f"{pid}" for pid in include_uuids)
        )
    ):
        with suppress(ValidationError):
            yield ProjectAtDB.model_validate(row)


async def project_exists(
    conn: SAConnection,
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
