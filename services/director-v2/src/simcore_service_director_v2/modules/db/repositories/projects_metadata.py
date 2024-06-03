from typing import Any

from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from simcore_postgres_database.utils_projects_metadata import ProjectMetadata
from simcore_postgres_database.utils_projects_metadata import (
    get as projects_metadata_get,
)

from ._base import BaseRepository


class ProjectsMetadataRepository(BaseRepository):
    async def get_custom_metadata(self, project_id: ProjectID) -> dict[str, Any] | None:
        """
        Raises:
            DBProjectNotFoundError
        """
        async with self.db_engine.acquire() as conn:
            project_metadata: ProjectMetadata = await projects_metadata_get(
                conn, project_id
            )
        custom_metadata: dict[str, Any] | None = project_metadata.custom
        return custom_metadata

    async def get_parent_project_and_node(
        self, project_id: ProjectID
    ) -> tuple[ProjectID, NodeID] | None:
        async with self.db_engine.acquire() as conn:
            project_metadata: ProjectMetadata = await projects_metadata_get(
                conn, project_id
            )
        if project_metadata.parent_project_uuid and project_metadata.parent_node_id:
            return project_metadata.parent_project_uuid, project_metadata.parent_node_id
        return None
