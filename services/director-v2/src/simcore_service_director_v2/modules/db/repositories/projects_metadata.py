from typing import Any

from models_library.projects import ProjectID
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
            project_custom_metadata = await projects_metadata_get(conn, project_id)
        return project_custom_metadata.custom
