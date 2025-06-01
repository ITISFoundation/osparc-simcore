import sqlalchemy
import sqlalchemy as sa
from aiohttp import web
from aiopg.sa.engine import Engine
from models_library.groups import GroupID
from models_library.projects import ProjectID
from models_library.users import UserID
from models_library.workspaces import WorkspaceID
from simcore_postgres_database.models.project_to_groups import project_to_groups
from simcore_postgres_database.models.projects import projects
from simcore_postgres_database.models.workspace_access_rights import (
    workspace_access_rights,
)
from simcore_postgres_database.utils_repos import (
    pass_or_acquire_connection,
)
from sqlalchemy.ext.asyncio import AsyncConnection

from ..db.plugin import get_asyncpg_engine
from .exceptions import ProjectNotFoundError


async def get_project_owner(engine: Engine, project_uuid: ProjectID) -> UserID:
    async with engine.acquire() as connection:
        stmt = sqlalchemy.select(projects.c.prj_owner).where(
            projects.c.uuid == f"{project_uuid}"
        )

        owner_id = await connection.scalar(stmt)
        if owner_id is None:
            raise ProjectNotFoundError(project_uuid=project_uuid)
        assert isinstance(owner_id, int)
        return owner_id


async def batch_get_project_access_rights(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    projects_uuids_with_workspace_id: list[
        tuple[ProjectID, WorkspaceID | None]
    ],  # list of tuples (project_uuid, workspace_id)
) -> dict[ProjectID, dict[GroupID, dict[str, bool]]]:
    # Split into private and shared workspace project IDs
    private_project_ids = [
        pid for pid, wid in projects_uuids_with_workspace_id if wid is None
    ]
    shared_project_ids = [
        pid for pid, wid in projects_uuids_with_workspace_id if wid is not None
    ]

    results = {}

    async with pass_or_acquire_connection(get_asyncpg_engine(app), connection) as conn:
        # Query private workspace projects
        if private_project_ids:
            private_query = (
                sa.select(
                    project_to_groups.c.project_uuid,
                    sa.func.jsonb_object_agg(
                        project_to_groups.c.gid,
                        sa.func.jsonb_build_object(
                            "read",
                            project_to_groups.c.read,
                            "write",
                            project_to_groups.c.write,
                            "delete",
                            project_to_groups.c.delete,
                        ),
                    ).label("access_rights"),
                )
                .where(
                    project_to_groups.c.project_uuid.in_(
                        [f"{uuid}" for uuid in private_project_ids]
                    )
                )
                .group_by(project_to_groups.c.project_uuid)
            )
            private_result = await conn.stream(private_query)
            async for row in private_result:
                results[row.project_uuid] = row.access_rights

        # Query shared workspace projects
        if shared_project_ids:
            shared_query = (
                sa.select(
                    workspace_access_rights.c.project_uuid,
                    sa.func.jsonb_object_agg(
                        workspace_access_rights.c.gid,
                        sa.func.jsonb_build_object(
                            "read",
                            workspace_access_rights.c.read,
                            "write",
                            workspace_access_rights.c.write,
                            "delete",
                            workspace_access_rights.c.delete,
                        ),
                    ).label("access_rights"),
                )
                .where(
                    workspace_access_rights.c.project_uuid.in_(
                        [f"{uuid}" for uuid in shared_project_ids]
                    )
                )
                .group_by(workspace_access_rights.c.project_uuid)
            )
            shared_result = await conn.stream(shared_query)
            async for row in shared_result:
                results[row.project_uuid] = row.access_rights

    return results
