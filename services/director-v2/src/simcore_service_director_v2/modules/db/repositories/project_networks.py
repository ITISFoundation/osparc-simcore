import sqlalchemy as sa
from aiopg.sa.result import RowProxy
from models_library.project_networks import ProjectNetworks
from models_library.projects import ProjectID

from ....core.errors import ProjectNotFoundError
from ..tables import project_networks
from ._base import BaseRepository


class ProjectNetworksRepository(BaseRepository):
    async def get_project_networks(self, project_id: ProjectID) -> ProjectNetworks:
        async with self.db_engine.acquire() as conn:
            row: RowProxy = await (
                await conn.execute(
                    sa.select([project_networks]).where(
                        project_networks.c.project_uuid == f"{project_id}"
                    )
                )
            ).first()
        if not row:
            raise ProjectNotFoundError(project_id)
        return ProjectNetworks.from_orm(row)
