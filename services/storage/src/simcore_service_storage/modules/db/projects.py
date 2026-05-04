from collections.abc import AsyncIterator
from typing import NamedTuple

import sqlalchemy as sa
from models_library.projects import ProjectID, ProjectIDStr
from models_library.projects_nodes_io import NodeIDStr
from simcore_postgres_database.models.projects_nodes import projects_nodes
from simcore_postgres_database.storage_models import projects
from simcore_postgres_database.utils_repos import pass_or_acquire_connection
from sqlalchemy.ext.asyncio import AsyncConnection

from ._base import BaseRepository


class ProjectNameTuple(NamedTuple):
    uuid: ProjectID
    name: str


class ProjectRepository(BaseRepository):
    async def list_project_names(
        self,
        *,
        connection: AsyncConnection | None = None,
        include_uuids: list[ProjectID],
    ) -> AsyncIterator[ProjectNameTuple]:
        async with pass_or_acquire_connection(self.db_engine, connection) as conn:
            async for row in await conn.stream(
                sa.select(projects.c.uuid, projects.c.name).where(
                    projects.c.uuid.in_(f"{pid}" for pid in include_uuids)
                )
            ):
                yield ProjectNameTuple(uuid=ProjectID(f"{row.uuid}"), name=row.name)

    async def project_exists(
        self,
        *,
        connection: AsyncConnection | None = None,
        project_uuid: ProjectID,
    ) -> bool:
        async with pass_or_acquire_connection(self.db_engine, connection) as conn:
            return bool(
                await conn.scalar(
                    sa.select(sa.func.count()).select_from(projects).where(projects.c.uuid == f"{project_uuid}")
                )
                == 1
            )

    async def get_project_id_and_node_id_to_names_map(
        self,
        *,
        connection: AsyncConnection | None = None,
        project_uuids: list[ProjectID],
    ) -> dict[ProjectID, dict[ProjectIDStr | NodeIDStr, str]]:
        mapping: dict[ProjectID, dict[ProjectIDStr | NodeIDStr, str]] = {}
        async with pass_or_acquire_connection(self.db_engine, connection) as conn:
            # Get project names
            async for row in await conn.stream(
                sa.select(projects.c.uuid, projects.c.name).where(
                    projects.c.uuid.in_(f"{pid}" for pid in project_uuids)
                )
            ):
                mapping[ProjectID(f"{row.uuid}")] = {f"{row.uuid}": row.name}

            # Get node labels from projects_nodes
            async for row in await conn.stream(
                sa.select(
                    projects_nodes.c.project_uuid,
                    projects_nodes.c.node_id,
                    projects_nodes.c.label,
                ).where(projects_nodes.c.project_uuid.in_(f"{pid}" for pid in project_uuids))
            ):
                project_id = ProjectID(f"{row.project_uuid}")
                if project_id in mapping:
                    mapping[project_id][f"{row.node_id}"] = row.label

        return mapping
