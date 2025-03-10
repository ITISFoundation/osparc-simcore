from collections.abc import AsyncIterator
from contextlib import suppress

import sqlalchemy as sa
from models_library.projects import ProjectAtDB, ProjectID, ProjectIDStr
from models_library.projects_nodes_io import NodeIDStr
from pydantic import ValidationError
from simcore_postgres_database.storage_models import projects
from sqlalchemy.ext.asyncio import AsyncConnection


async def list_valid_projects_in(
    conn: AsyncConnection,
    include_uuids: list[ProjectID],
) -> AsyncIterator[ProjectAtDB]:
    """

    NOTE that it lists ONLY validated projects in 'project_uuids'
    """
    async for row in await conn.stream(
        sa.select(projects).where(
            projects.c.uuid.in_(f"{pid}" for pid in include_uuids)
        )
    ):
        with suppress(ValidationError):
            yield ProjectAtDB.model_validate(row)


async def project_exists(
    conn: AsyncConnection,
    project_uuid: ProjectID,
) -> bool:
    return bool(
        await conn.scalar(
            sa.select(sa.func.count())
            .select_from(projects)
            .where(projects.c.uuid == f"{project_uuid}")
        )
        == 1
    )


async def get_project_id_and_node_id_to_names_map(
    conn: AsyncConnection, project_uuids: list[ProjectID]
) -> dict[ProjectID, dict[ProjectIDStr | NodeIDStr, str]]:
    mapping = {}
    async for row in await conn.stream(
        sa.select(projects.c.uuid, projects.c.name, projects.c.workbench).where(
            projects.c.uuid.in_(f"{pid}" for pid in project_uuids)
        )
    ):
        mapping[ProjectID(f"{row.uuid}")] = {f"{row.uuid}": row.name} | {
            f"{node_id}": node["label"] for node_id, node in row.workbench.items()
        }

    return mapping
