from collections.abc import AsyncIterator
from contextlib import suppress

import sqlalchemy as sa
from models_library.projects import ProjectAtDB, ProjectID, ProjectIDStr
from models_library.projects_nodes_io import NodeIDStr
from pydantic import ValidationError
from simcore_postgres_database.storage_models import projects
from simcore_postgres_database.utils_repos import pass_or_acquire_connection
from sqlalchemy.ext.asyncio import AsyncConnection

from ._base import BaseRepository


class ProjectRepository(BaseRepository):
    async def list_valid_projects_in(
        self,
        *,
        connection: AsyncConnection | None = None,
        include_uuids: list[ProjectID],
    ) -> AsyncIterator[ProjectAtDB]:
        """

        NOTE that it lists ONLY validated projects in 'project_uuids'
        """
        async with pass_or_acquire_connection(self.db_engine, connection) as conn:
            async for row in await conn.stream(
                sa.select(projects).where(
                    projects.c.uuid.in_(f"{pid}" for pid in include_uuids)
                )
            ):
                with suppress(ValidationError):
                    yield ProjectAtDB.model_validate(row)

    async def project_exists(
        self,
        *,
        connection: AsyncConnection | None = None,
        project_uuid: ProjectID,
    ) -> bool:
        async with pass_or_acquire_connection(self.db_engine, connection) as conn:
            return bool(
                await conn.scalar(
                    sa.select(sa.func.count())
                    .select_from(projects)
                    .where(projects.c.uuid == f"{project_uuid}")
                )
                == 1
            )

    async def get_project_id_and_node_id_to_names_map(
        self,
        *,
        connection: AsyncConnection | None = None,
        project_uuids: list[ProjectID],
    ) -> dict[ProjectID, dict[ProjectIDStr | NodeIDStr, str]]:
        mapping = {}
        async with pass_or_acquire_connection(self.db_engine, connection) as conn:
            async for row in await conn.stream(
                sa.select(projects.c.uuid, projects.c.name, projects.c.workbench).where(
                    projects.c.uuid.in_(f"{pid}" for pid in project_uuids)
                )
            ):
                mapping[ProjectID(f"{row.uuid}")] = {f"{row.uuid}": row.name} | {
                    f"{node_id}": node["label"]
                    for node_id, node in row.workbench.items()
                }

        return mapping
