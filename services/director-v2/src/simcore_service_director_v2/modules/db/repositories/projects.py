import logging

import sqlalchemy as sa
from aiopg.sa.result import RowProxy
from models_library.projects import ProjectAtDB, ProjectID
from models_library.projects_nodes_io import NodeID

from ....core.errors import ProjectNotFoundError
from ..tables import projects
from ._base import BaseRepository

logger = logging.getLogger(__name__)


class ProjectsRepository(BaseRepository):
    async def get_project(self, project_id: ProjectID) -> ProjectAtDB:
        async with self.db_engine.acquire() as conn:
            row: RowProxy = await (
                await conn.execute(
                    sa.select([projects]).where(projects.c.uuid == str(project_id))
                )
            ).first()
        if not row:
            raise ProjectNotFoundError(project_id)
        return ProjectAtDB.from_orm(row)

    async def is_node_present_in_workbench(
        self, project_id: ProjectID, node_uuid: NodeID
    ) -> bool:
        try:
            project = await self.get_project(project_id)
            return f"{node_uuid}" in project.workbench
        except ProjectNotFoundError:
            return False
