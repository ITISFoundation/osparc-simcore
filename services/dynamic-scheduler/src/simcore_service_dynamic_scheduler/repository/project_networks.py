import sqlalchemy as sa
from common_library.errors_classes import OsparcErrorMixin
from models_library.projects import ProjectID
from models_library.projects_networks import NetworksWithAliases, ProjectsNetworks
from simcore_postgres_database.models.projects_networks import projects_networks
from simcore_postgres_database.utils_repos import (
    pass_or_acquire_connection,
    transaction_context,
)
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine


class BaseProjectNetwroksError(OsparcErrorMixin, RuntimeError):
    msg_template: str = "project networks unexpected error"


class ProjectNetworkNotFoundError(BaseProjectNetwroksError):
    msg_template: str = "no networks found for project {project_id}"


class ProjectNetworksRepo:
    def __init__(self, engine: AsyncEngine):
        self.engine = engine

    async def get_projects_networks(
        self, connection: AsyncConnection | None = None, *, project_id: ProjectID
    ) -> ProjectsNetworks:
        async with pass_or_acquire_connection(self.engine, connection) as conn:
            result = await conn.execute(
                sa.select(projects_networks).where(
                    projects_networks.c.project_uuid == f"{project_id}"
                )
            )
            row = result.first()
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
            {"project_uuid": project_id, "networks_with_aliases": networks_with_aliases}
        )

        async with transaction_context(self.engine, connection) as conn:
            row_data = projects_networks_to_insert.model_dump(mode="json")
            insert_stmt = pg_insert(projects_networks).values(**row_data)
            upsert_snapshot = insert_stmt.on_conflict_do_update(
                index_elements=[projects_networks.c.project_uuid], set_=row_data
            )
            await conn.execute(upsert_snapshot)
