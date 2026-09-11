import logging

import sqlalchemy as sa
from models_library.projects import ProjectAtDB, ProjectID
from simcore_postgres_database.utils_repos import pass_or_acquire_connection

from ....core.errors import ProjectNotFoundError
from ..tables import projects
from ._base import BaseRepository

logger = logging.getLogger(__name__)


class ProjectsRepository(BaseRepository):
    async def exists(self, project_id: ProjectID) -> bool:
        async with pass_or_acquire_connection(self.db_engine) as conn:
            stmt = sa.select(sa.exists(sa.select(sa.literal(1)).where(projects.c.uuid == f"{project_id}")))
            result = await conn.execute(stmt)
            return result.scalar_one()

    async def get(self, project_id: ProjectID) -> ProjectAtDB:
        async with pass_or_acquire_connection(self.db_engine) as conn:
            stmt = sa.select(projects).where(projects.c.uuid == f"{project_id}")
            result = await conn.execute(stmt)
            row = result.one_or_none()
            if row is None:
                raise ProjectNotFoundError(project_id=project_id)
            return ProjectAtDB.model_validate(row)
