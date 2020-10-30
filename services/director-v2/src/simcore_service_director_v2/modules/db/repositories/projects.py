import logging

import sqlalchemy as sa
from aiopg.sa.result import RowProxy
from models_library.projects import ProjectID

from ....models.domains.projects import ProjectAtDB
from ....utils.exceptions import ProjectNotFoundError
from ..tables import projects
from ._base import BaseRepository

logger = logging.getLogger(__name__)


class ProjectsRepository(BaseRepository):
    async def get_project(self, project_id: ProjectID) -> ProjectAtDB:
        row: RowProxy = await (
            await self.connection.execute(
                sa.select([projects]).where(projects.c.uuid == str(project_id))
            )
        ).first()
        if not row:
            raise ProjectNotFoundError(project_id)
        return ProjectAtDB.from_orm(row)
