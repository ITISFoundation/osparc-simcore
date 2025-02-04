import logging

import sqlalchemy as sa
from aiopg.sa.result import RowProxy
from models_library.projects import ProjectAtDB, ProjectID

from ....core.errors import ProjectNotFoundError
from ..tables import projects
from ._base import BaseRepository

logger = logging.getLogger(__name__)


class ProjectsRepository(BaseRepository):
    async def get_project(self, project_id: ProjectID) -> ProjectAtDB:
        async with self.db_engine.acquire() as conn:
            row: RowProxy | None = await (
                await conn.execute(
                    sa.select(projects).where(projects.c.uuid == str(project_id))
                )
            ).first()
        if not row:
            raise ProjectNotFoundError(project_id=project_id)
        return ProjectAtDB.model_validate(row)
