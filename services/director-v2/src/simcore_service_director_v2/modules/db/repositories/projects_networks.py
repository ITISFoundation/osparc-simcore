import json

import sqlalchemy as sa
from aiopg.sa.result import RowProxy
from models_library.projects import ProjectID
from models_library.projects_networks import NetworksWithAliases, ProjectsNetworks
from sqlalchemy.dialects.postgresql import insert as pg_insert

from ....core.errors import ProjectNetworkNotFoundError
from ..tables import projects_networks
from ._base import BaseRepository


class ProjectsNetworksRepository(BaseRepository):
    async def get_projects_networks(self, project_id: ProjectID) -> ProjectsNetworks:
        async with self.db_engine.acquire() as conn:
            row: RowProxy | None = await (
                await conn.execute(
                    sa.select(projects_networks).where(
                        projects_networks.c.project_uuid == f"{project_id}"
                    )
                )
            ).first()
        if not row:
            raise ProjectNetworkNotFoundError(project_id=project_id)
        return ProjectsNetworks.model_validate(row)

    async def upsert_projects_networks(
        self, project_id: ProjectID, networks_with_aliases: NetworksWithAliases
    ) -> None:
        projects_networks_to_insert = ProjectsNetworks.model_validate(
            {"project_uuid": project_id, "networks_with_aliases": networks_with_aliases}
        )

        async with self.db_engine.acquire() as conn:
            row_data = json.loads(projects_networks_to_insert.model_dump_json())
            insert_stmt = pg_insert(projects_networks).values(**row_data)
            upsert_snapshot = insert_stmt.on_conflict_do_update(
                constraint=projects_networks.primary_key, set_=row_data
            )
            await conn.execute(upsert_snapshot)
