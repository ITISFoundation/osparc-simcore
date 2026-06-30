from typing import Final

import sqlalchemy as sa
from models_library.projects import NodesDict, ProjectID
from models_library.projects_nodes import Node
from models_library.projects_nodes_io import NodeID
from simcore_postgres_database.utils_repos import pass_or_acquire_connection

from ....core.errors import ProjectNodeNotFoundError
from ...db.repositories import BaseRepository
from ..tables import projects_nodes

_NODE_COLUMNS: Final = (
    projects_nodes.c.key,
    projects_nodes.c.version,
    projects_nodes.c.label,
    projects_nodes.c.progress,
    projects_nodes.c.thumbnail,
    projects_nodes.c.input_access,
    projects_nodes.c.input_nodes,
    projects_nodes.c.inputs,
    projects_nodes.c.inputs_required,
    projects_nodes.c.inputs_units,
    projects_nodes.c.outputs,
    projects_nodes.c.run_hash,
    projects_nodes.c.state,
    projects_nodes.c.boot_options,
)


class ProjectsNodesRepository(BaseRepository):
    async def exists(self, project_id: ProjectID, node_id: NodeID) -> bool:
        async with pass_or_acquire_connection(self.db_engine) as conn:
            stmt = sa.select(
                sa.exists().where(
                    projects_nodes.c.project_uuid == f"{project_id}",
                    projects_nodes.c.node_id == f"{node_id}",
                )
            )
            result = await conn.execute(stmt)
            return result.scalar_one()

    async def get(self, project_id: ProjectID, node_id: NodeID) -> Node:
        async with pass_or_acquire_connection(self.db_engine) as conn:
            stmt = sa.select(*_NODE_COLUMNS).where(
                projects_nodes.c.project_uuid == f"{project_id}",
                projects_nodes.c.node_id == f"{node_id}",
            )
            result = await conn.execute(stmt)
            row = result.mappings().one_or_none()
            if row is None:
                raise ProjectNodeNotFoundError(project_id=project_id, node_id=node_id)
            return Node.model_validate(row)

    async def get_all(self, project_id: ProjectID) -> NodesDict:
        async with pass_or_acquire_connection(self.db_engine) as conn:
            stmt = sa.select(projects_nodes.c.node_id, *_NODE_COLUMNS).where(
                projects_nodes.c.project_uuid == f"{project_id}"
            )
            result = await conn.execute(stmt)
            return {
                f"{row['node_id']}": Node.model_validate({k: v for k, v in row.items() if k != "node_id"})
                for row in result.mappings()
            }

    async def list_nodes_ids(self, project_id: ProjectID) -> list[NodeID]:
        async with pass_or_acquire_connection(self.db_engine) as conn:
            stmt = sa.select(projects_nodes.c.node_id).where(projects_nodes.c.project_uuid == f"{project_id}")
            result = await conn.execute(stmt)
            return [NodeID(node_id) for node_id in result.scalars()]
