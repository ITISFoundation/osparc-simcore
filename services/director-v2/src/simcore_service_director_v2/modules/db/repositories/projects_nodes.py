import sqlalchemy as sa
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from simcore_postgres_database.utils_repos import pass_or_acquire_connection

from ...db.repositories import BaseRepository
from ..tables import projects_nodes


class ProjectsNodesRepository(BaseRepository):
    async def list_nodes_ids(self, project_id: ProjectID) -> list[NodeID]:
        async with pass_or_acquire_connection(self.db_engine) as conn:
            stmt = sa.select(projects_nodes.c.node_id).where(projects_nodes.c.project_uuid == f"{project_id}")
            result = await conn.execute(stmt)
            return [NodeID(node_id) for node_id in result.scalars()]
