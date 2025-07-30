from collections.abc import AsyncIterator
from contextlib import suppress

import sqlalchemy as sa
from models_library.projects import ProjectAtDB, ProjectID, ProjectIDStr
from models_library.projects_nodes_io import NodeIDStr
from pydantic import ValidationError
from simcore_postgres_database.models.projects_nodes import projects_nodes
from simcore_postgres_database.storage_models import projects
from simcore_postgres_database.utils_repos import pass_or_acquire_connection
from sqlalchemy.ext.asyncio import AsyncConnection

from ._base import BaseRepository


class ProjectRepository(BaseRepository):
    async def list_valid_projects_in(
        self,
        *,
        connection: AsyncConnection | None = None,
        project_uuids: list[ProjectID],
    ) -> AsyncIterator[ProjectAtDB]:
        """

        NOTE that it lists ONLY validated projects in 'project_uuids'
        """
        async with pass_or_acquire_connection(self.db_engine, connection) as conn:
            async for row in await conn.stream(
                sa.select(projects).where(
                    projects.c.uuid.in_(f"{pid}" for pid in project_uuids)
                )
            ):
                with suppress(ValidationError):
                    yield ProjectAtDB.model_validate_ignoring_workbench(row._asdict())

    async def get_project_id_and_node_id_to_names_map(
        self,
        *,
        connection: AsyncConnection | None = None,
        project_uuids: list[ProjectID],
    ) -> dict[ProjectID, dict[ProjectIDStr | NodeIDStr, str]]:
        names_map = {}
        async with pass_or_acquire_connection(self.db_engine, connection) as conn:
            async for row in await conn.stream(
                sa.select(projects.c.uuid, projects.c.name).where(
                    projects.c.uuid.in_(f"{pid}" for pid in project_uuids)
                )
            ):
                names_map[ProjectID(row.uuid)] = {f"{row.uuid}": row.name}

            async for row in await conn.stream(
                sa.select(
                    projects_nodes.c.node_id,
                    projects_nodes.c.project_uuid,
                    projects_nodes.c.label,
                ).where(
                    projects_nodes.c.project_uuid.in_(
                        [f"{project_uuid}" for project_uuid in project_uuids]
                    )
                )
            ):
                names_map[ProjectID(row.project_uuid)] |= {f"{row.node_id}": row.label}

        return names_map
