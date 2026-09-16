import logging

import sqlalchemy as sa
from models_library.projects import ProjectAtDB, ProjectID
from simcore_postgres_database.utils_repos import pass_or_acquire_connection
from sqlalchemy.ext.asyncio import AsyncConnection

from ....core.errors import ProjectNotFoundError
from ..tables import projects
from ._base import BaseRepository

logger = logging.getLogger(__name__)


class ProjectsRepository(BaseRepository):
    async def exists(
        self,
        connection: AsyncConnection | None = None,
        *,
        project_id: ProjectID,
    ) -> bool:
        async with pass_or_acquire_connection(self.db_engine, connection) as conn:
            stmt = sa.select(sa.exists().where(projects.c.uuid == f"{project_id}"))
            result = await conn.execute(stmt)
            return result.scalar_one()

    async def get(
        self,
        connection: AsyncConnection | None = None,
        *,
        project_id: ProjectID,
    ) -> ProjectAtDB:
        async with pass_or_acquire_connection(self.db_engine, connection) as conn:
            query = sa.select(
                projects,
            ).where(projects.c.uuid == str(project_id))
            result = await conn.execute(query)
            row = result.one_or_none()
            if row is None:
                raise ProjectNotFoundError(project_id=project_id)
            return ProjectAtDB.model_validate(row)
