import sqlalchemy
import sqlalchemy as sa
from aiohttp import web
from aiopg.sa.engine import Engine
from models_library.groups import GroupID
from models_library.projects import ProjectID, ProjectIDStr
from models_library.users import UserID
from models_library.workspaces import WorkspaceID
from simcore_postgres_database.models.project_to_groups import project_to_groups
from simcore_postgres_database.models.projects import projects
from simcore_postgres_database.models.workspaces_access_rights import (
    workspaces_access_rights,
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


def _split_private_and_shared_projects(
    projects_uuids_with_workspace_id: list[tuple[ProjectID, WorkspaceID | None]],
) -> tuple[list[ProjectID], dict[WorkspaceID, list[ProjectID]]]:
    """Splits project tuples into private project IDs and a mapping of workspace_id to project IDs."""
    private_project_ids = []
    workspace_to_project_ids: dict[WorkspaceID, list[ProjectID]] = {}
    for pid, wid in projects_uuids_with_workspace_id:
        if wid is None:
            private_project_ids.append(pid)
        else:
            workspace_to_project_ids.setdefault(wid, []).append(pid)
    return private_project_ids, workspace_to_project_ids


async def batch_get_project_access_rights(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    projects_uuids_with_workspace_id: list[tuple[ProjectID, WorkspaceID | None]],
) -> dict[ProjectIDStr, dict[GroupID, dict[str, bool]]]:
    private_project_ids, workspace_to_project_ids = _split_private_and_shared_projects(
        projects_uuids_with_workspace_id
    )
    shared_workspace_ids = set(workspace_to_project_ids.keys())
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

        # Query shared workspace projects by workspace_id
        if shared_workspace_ids:
            shared_query = (
                sa.select(
                    workspaces_access_rights.c.workspace_id,
                    sa.func.jsonb_object_agg(
                        workspaces_access_rights.c.gid,
                        sa.func.jsonb_build_object(
                            "read",
                            workspaces_access_rights.c.read,
                            "write",
                            workspaces_access_rights.c.write,
                            "delete",
                            workspaces_access_rights.c.delete,
                        ),
                    ).label("access_rights"),
                )
                .where(
                    workspaces_access_rights.c.workspace_id.in_(shared_workspace_ids)
                )
                .group_by(workspaces_access_rights.c.workspace_id)
            )
            shared_result = await conn.stream(shared_query)
            workspace_access_rights_map = {}
            async for row in shared_result:
                workspace_access_rights_map[row.workspace_id] = row.access_rights
            # Assign access rights to each project in the workspace
            for wid, project_ids in workspace_to_project_ids.items():
                access_rights = workspace_access_rights_map.get(wid)
                if access_rights is not None:
                    for pid in project_ids:
                        results[f"{pid}"] = access_rights

    return results
