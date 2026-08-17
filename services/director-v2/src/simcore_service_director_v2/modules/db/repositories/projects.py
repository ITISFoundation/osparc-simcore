import logging

import sqlalchemy as sa
from models_library.projects import ProjectAtDB, ProjectID
from models_library.projects_nodes_io import NodeID
from simcore_postgres_database.utils_projects_nodes import ProjectNodesRepo
from simcore_postgres_database.utils_repos import pass_or_acquire_connection

from ....core.errors import ProjectNotFoundError
from ..tables import projects
from ._base import BaseRepository

logger = logging.getLogger(__name__)


class ProjectsRepository(BaseRepository):
    async def exists(self, project_id: ProjectID) -> bool:
        async with pass_or_acquire_connection(self.db_engine) as conn:
            stmt = sa.select(sa.exists().where(projects.c.uuid == f"{project_id}"))
            result = await conn.execute(stmt)
            return result.scalar_one()

    async def get(self, project_id: ProjectID) -> ProjectAtDB:
        # Select all project columns except 'workbench' (deprecated).
        # The workbench is no longer reconstructed here for performance reasons;
        # callers that need the nodes must fetch them via ProjectsNodesRepository.
        project_cols = [c for c in projects.c if c.name != "workbench"]

        async with pass_or_acquire_connection(self.db_engine) as conn:
            query = sa.select(
                *project_cols,
            ).where(projects.c.uuid == str(project_id))
            result = await conn.execute(query)
            row = result.one_or_none()
            if row is None:
                raise ProjectNotFoundError(project_id=project_id)
            return ProjectAtDB.model_validate(row)

    async def get_project_id_from_node(self, node_id: NodeID) -> ProjectID:
        async with pass_or_acquire_connection(self.db_engine) as conn:
            return await ProjectNodesRepo.get_project_id_from_node_id(conn, node_id=node_id)
