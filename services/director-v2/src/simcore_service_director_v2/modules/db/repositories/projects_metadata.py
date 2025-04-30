from dataclasses import dataclass

from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from simcore_postgres_database.utils_projects_metadata import (
    get as projects_metadata_get,
)

from ._base import BaseRepository


@dataclass(frozen=True, kw_only=True, slots=True)
class ProjectAncestors:
    parent_project_uuid: ProjectID | None
    parent_node_id: NodeID | None
    root_project_uuid: ProjectID | None
    root_node_id: NodeID | None


class ProjectsMetadataRepository(BaseRepository):
    async def get_project_ancestors(self, project_id: ProjectID) -> ProjectAncestors:
        """
        Raises:
            DBProjectNotFoundError: project not found
        """
        async with self.db_engine.connect() as conn:
            project_metadata = await projects_metadata_get(conn, project_id)
        return ProjectAncestors(
            parent_project_uuid=project_metadata.parent_project_uuid,
            parent_node_id=project_metadata.parent_node_id,
            root_project_uuid=project_metadata.root_parent_project_uuid,
            root_node_id=project_metadata.root_parent_node_id,
        )
