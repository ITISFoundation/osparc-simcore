import logging

import sqlalchemy as sa
from models_library.projects import NodesDict, ProjectID
from models_library.projects_nodes import Node, NodeID
from simcore_postgres_database.utils_projects_nodes import (
    ProjectNode,
    ProjectNodesNodeNotFoundError,
)

from ..tables import projects_nodes
from ._base import BaseRepository

logger = logging.getLogger(__name__)


class ProjectsNodesRepository(BaseRepository):
    async def get_nodes(self, project_id: ProjectID) -> NodesDict:
        nodes_dict = {}
        async with self.db_engine.acquire() as conn:
            rows = await (
                await conn.execute(
                    sa.select(projects_nodes).where(
                        projects_nodes.c.project_uuid == f"{project_id}"
                    )
                )
            ).fetchall()

            for row in rows:
                nodes_dict[f"{row.node_id}"] = Node.model_validate(
                    ProjectNode.model_validate(row, from_attributes=True).model_dump(
                        exclude={
                            "node_id",
                            "required_resources",
                            "created",
                            "modified",
                        },
                        exclude_none=True,
                        exclude_unset=True,
                    )
                )

        return nodes_dict

    async def exists_node(self, project_id: ProjectID, node_id: NodeID) -> bool:
        async with self.db_engine.acquire() as conn:
            result = await (
                await conn.execute(
                    sa.select(projects_nodes).where(
                        (projects_nodes.c.project_uuid == f"{project_id}")
                        & (projects_nodes.c.node_id == f"{node_id}")
                    )
                )
            ).fetchone()
            return result is not None

    async def get_project_id_from_node(self, node_id: NodeID) -> ProjectID:
        async with self.db_engine.acquire() as conn:
            result = await (
                await conn.execute(
                    sa.select(projects_nodes.c.project_uuid).where(
                        projects_nodes.c.node_id == f"{node_id}"
                    )
                )
            ).fetchone()
            if result is None:
                raise ProjectNodesNodeNotFoundError(node_id=node_id)

            return ProjectID(result[0])
