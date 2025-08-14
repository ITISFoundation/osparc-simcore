import logging

import sqlalchemy as sa
from models_library.projects import ProjectAtDB, ProjectID
from models_library.projects_nodes_io import NodeID
from simcore_postgres_database.utils_projects_nodes import (
    ProjectNodesRepo,
    make_workbench_subquery,
)
from simcore_postgres_database.utils_repos import pass_or_acquire_connection

from ....core.errors import ProjectNotFoundError
from ..tables import projects, projects_nodes
from ._base import BaseRepository

logger = logging.getLogger(__name__)


class ProjectsRepository(BaseRepository):
    async def get_project(self, project_id: ProjectID) -> ProjectAtDB:
        workbench_subquery = make_workbench_subquery()

        async with self.db_engine.connect() as conn:
            query = (
                sa.select(
                    projects,
                    sa.func.coalesce(
                        workbench_subquery.c.workbench, sa.text("'{}'::json")
                    ).label("workbench"),
                )
                .select_from(
                    projects.outerjoin(
                        workbench_subquery,
                        projects.c.uuid == workbench_subquery.c.project_uuid,
                    )
                )
                .where(projects.c.uuid == str(project_id))
            )
            result = await conn.execute(query)
            row = result.one_or_none()
            if not row:
                raise ProjectNotFoundError(project_id=project_id)
            return ProjectAtDB.model_validate(row)

    async def is_node_present_in_workbench(
        self, project_id: ProjectID, node_uuid: NodeID
    ) -> bool:
        async with pass_or_acquire_connection(self.db_engine) as conn:
            stmt = (
                sa.select(sa.literal(1))
                .where(
                    projects_nodes.c.project_uuid == str(project_id),
                    projects_nodes.c.node_id == str(node_uuid),
                )
                .limit(1)
            )

            result = await conn.execute(stmt)
            return result.scalar_one_or_none() is not None

    async def get_project_id_from_node(self, node_id: NodeID) -> ProjectID:
        async with self.db_engine.connect() as conn:
            return await ProjectNodesRepo.get_project_id_from_node_id(
                conn, node_id=node_id
            )
