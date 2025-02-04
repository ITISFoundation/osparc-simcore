import logging

import sqlalchemy as sa
from models_library.projects import NodesDict, ProjectID
from models_library.projects_nodes import Node
from simcore_postgres_database.utils_projects_nodes import ProjectNode

from ..tables import projects_nodes
from ._base import BaseRepository

logger = logging.getLogger(__name__)


class ProjectsNodesRepository(BaseRepository):
    async def get_nodes(self, project_uuid: ProjectID) -> NodesDict:
        nodes_dict = {}
        async with self.db_engine.acquire() as conn:
            rows = await (
                await conn.execute(
                    sa.select(projects_nodes).where(
                        projects_nodes.c.project_uuid == f"{project_uuid}"
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

    # async def is_node_present_in_workbench(
    #     self, project_id: ProjectID, node_uuid: NodeID
    # ) -> bool:
    #     try:
    #         project = await self.get_project(project_id)
    #         return f"{node_uuid}" in project.workbench
    #     except ProjectNotFoundError:
    #         return False

    # async def get_project_id_from_node(self, node_id: NodeID) -> ProjectID:
    #     async with self.db_engine.acquire() as conn:
    #         return await ProjectNodesRepo.get_project_id_from_node_id(
    #             conn, node_id=node_id
    #         )
