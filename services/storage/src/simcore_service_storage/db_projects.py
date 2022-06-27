from typing import AsyncGenerator

import sqlalchemy as sa
from aiopg.sa.connection import SAConnection
from models_library.projects import ProjectAtDB, ProjectID
from simcore_postgres_database.models.projects import projects


# TODO: this still needs some love. ProjectAtDB is not happy there is something fishy here
# the generated projects in the failing tests have far too many fields???
async def list_projects(
    conn: SAConnection, project_uuids: list[ProjectID]
) -> AsyncGenerator[ProjectAtDB, None]:
    async for row in conn.execute(
        sa.select([projects]).where(
            projects.c.uuid.in_(f"{pid}" for pid in project_uuids)
        )
    ):
        yield ProjectAtDB.from_orm(row)
