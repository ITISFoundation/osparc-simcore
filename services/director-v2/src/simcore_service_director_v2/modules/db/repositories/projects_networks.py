import sqlalchemy as sa
from common_library.json_serialization import json_loads
from models_library.projects import ProjectID
from models_library.projects_networks import NetworksWithAliases, ProjectsNetworks
from simcore_postgres_database.utils_repos import pass_or_acquire_connection, transaction_context
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncConnection

from ....core.errors import ProjectNetworkNotFoundError
from ..tables import projects_networks
from ._base import BaseRepository


class ProjectsNetworksRepository(BaseRepository):
    async def get_projects_networks(
        self,
        connection: AsyncConnection | None = None,
        *,
        project_id: ProjectID,
    ) -> ProjectsNetworks:
        async with pass_or_acquire_connection(self.db_engine, connection) as conn:
            row = (
                await conn.execute(
                    sa.select(projects_networks).where(projects_networks.c.project_uuid == f"{project_id}")
                )
            ).one_or_none()
        if not row:
            raise ProjectNetworkNotFoundError(project_id=project_id)
        return ProjectsNetworks.model_validate(row)

    async def upsert_projects_networks(
        self,
        connection: AsyncConnection | None = None,
        *,
        project_id: ProjectID,
        networks_with_aliases: NetworksWithAliases,
    ) -> None:
        projects_networks_to_insert = ProjectsNetworks.model_validate(
            {
                "project_uuid": project_id,
                "networks_with_aliases": networks_with_aliases,
            }
        )
        row_data = json_loads(projects_networks_to_insert.model_dump_json())

        async with transaction_context(self.db_engine, connection) as conn:
            insert_stmt = pg_insert(projects_networks).values(**row_data)
            upsert_snapshot = insert_stmt.on_conflict_do_update(constraint=projects_networks.primary_key, set_=row_data)
            await conn.execute(upsert_snapshot)
