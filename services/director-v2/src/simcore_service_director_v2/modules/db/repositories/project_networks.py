import json

import sqlalchemy as sa
from aiopg.sa.result import RowProxy
from models_library.project_networks import NetworksWithAliases, ProjectNetworks
from models_library.projects import ProjectID
from sqlalchemy.dialects.postgresql import insert as pg_insert

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

    async def update_project_networks(
        self, project_id: ProjectID, networks_with_aliases: NetworksWithAliases
    ) -> None:
        project_networks_to_insert = ProjectNetworks.parse_obj(
            dict(project_uuid=project_id, networks_with_aliases=networks_with_aliases)
        )

        async with self.db_engine.acquire() as conn:
            row_data = json.loads(project_networks_to_insert.json())
            insert_stmt = pg_insert(project_networks).values(**row_data)
            upsert_snapshot = insert_stmt.on_conflict_do_update(
                constraint=project_networks.primary_key, set_=row_data
            )
            await conn.execute(upsert_snapshot)
