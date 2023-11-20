from typing import Any

from models_library.projects import ProjectID
from simcore_postgres_database.utils_projects_metadata import ProjectMetadata
from simcore_postgres_database.utils_projects_metadata import (
    get as projects_metadata_get,
)

from ._base import BaseRepository


class ProjectsMetadataRepository(BaseRepository):
    async def get_metadata(self, project_id: ProjectID) -> dict[str, Any] | None:
        """
        Raises:
            DBProjectNotFoundError
        """
        async with self.db_engine.acquire() as conn:
            project_custom_metadata: ProjectMetadata = await projects_metadata_get(
                conn, project_id
            )
        custom_metadata: dict[str, Any] | None = project_custom_metadata.custom
        return custom_metadata
