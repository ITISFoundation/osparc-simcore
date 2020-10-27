import logging

import sqlalchemy as sa
from aiopg.sa.result import RowProxy
from models_library.projects import ProjectAtDB

from ..tables import projects
from ._base import BaseRepository

logger = logging.getLogger(__name__)


class ProjectsRepository(BaseRepository):
    async def get_project(self, project_id: str) -> ProjectAtDB:
        row: RowProxy = await (
            await self.connection.execute(
                sa.select([projects]).where(projects.c.uuid == project_id)
            )
        ).first()
        return ProjectAtDB(**row)
