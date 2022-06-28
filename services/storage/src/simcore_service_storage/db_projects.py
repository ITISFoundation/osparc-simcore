from typing import AsyncGenerator

import sqlalchemy as sa
from aiopg.sa.connection import SAConnection
from models_library.projects import ProjectAtDB, ProjectID
from simcore_postgres_database.storage_models import projects


async def list_projects(
    conn: SAConnection, project_uuids: list[ProjectID]
) -> AsyncGenerator[ProjectAtDB, None]:
    async for row in conn.execute(
        sa.select([projects]).where(
            projects.c.uuid.in_(f"{pid}" for pid in project_uuids)
        )
    ):
        yield ProjectAtDB.from_orm(row)


async def project_exists(conn: SAConnection, project_uuid: ProjectID) -> bool:
    return (
        await conn.scalar(
            sa.select([sa.func.count()])
            .select_from(projects)
            .where(projects.c.uuid == f"{project_uuid}")
        )
        == 1
    )
