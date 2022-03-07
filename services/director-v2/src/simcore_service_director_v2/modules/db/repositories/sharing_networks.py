import sqlalchemy as sa
from aiopg.sa.result import RowProxy
from models_library.projects import ProjectID
from models_library.sharing_networks import SharingNetworks

from ....core.errors import ProjectNotFoundError
from ..tables import sharing_networks
from ._base import BaseRepository


class SharingNetworksRepository(BaseRepository):
    async def get_sharing_networks(self, project_id: ProjectID) -> SharingNetworks:
        async with self.db_engine.acquire() as conn:
            row: RowProxy = await (
                await conn.execute(
                    sa.select([sharing_networks]).where(
                        sharing_networks.c.project_uuid == f"{project_id}"
                    )
                )
            ).first()
        if not row:
            raise ProjectNotFoundError(project_id)
        return SharingNetworks.from_orm(row)
