from numpy import diff
import sqlalchemy
from aiopg.sa.engine import Engine
from models_library.projects import ProjectID
from models_library.users import UserID
from simcore_postgres_database.models.projects import projects
import logging
from collections.abc import Callable
from datetime import datetime
from typing import cast

import sqlalchemy as sa
from aiohttp import web
from common_library.exclude import UnSet, is_set
from models_library.basic_types import IDStr
from models_library.groups import GroupID
from models_library.projects import ProjectID
from models_library.rest_ordering import OrderBy, OrderDirection
from models_library.rest_pagination import MAXIMUM_NUMBER_OF_ITEMS_PER_PAGE
from models_library.workspaces import WorkspaceID
from pydantic import NonNegativeInt, PositiveInt
from simcore_postgres_database.models.projects import projects
from simcore_postgres_database.models.project_to_groups import project_to_groups
from simcore_postgres_database.models.users import users
from simcore_postgres_database.utils_repos import (
    get_columns_from_db_model,
    pass_or_acquire_connection,
    transaction_context,
)
from sqlalchemy import sql
from sqlalchemy.ext.asyncio import AsyncConnection

from ..db.plugin import get_asyncpg_engine
from .exceptions import ProjectNotFoundError
from .models import ProjectDBGet
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
    projects_uuids: list[ProjectID],
) -> dict[ProjectID, dict[GroupID, dict[str, bool]]]:

    # NOTE: MD: TODO: differentiate between private/shared workspaces
    # based on that use either project_to_groups or workspace_access_rights

    private_workspace_access_rights_query = (
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
            (projects.c.uuid.in_([f"{uuid}" for uuid in projects_uuids]))  # <-- this needs to be prefiltered based on workspace
            & (project_to_groups.c.read)
        )
        .group_by(project_to_groups.c.project_uuid)
    )

    shared_workspace_access_rights_query = (
        sa.select(
            workspace_access_rights.c.project_uuid,
            sa.func.jsonb_object_agg(
                project_to_groups.c.gid,
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
            (projects.c.uuid.in_([f"{uuid}" for uuid in projects_uuids]))  # <-- this needs to be prefiltered based on workspace
            & (workspace_access_rights.c.read)
        )
        .group_by(workspace_access_rights.c.project_uuid)
    )

    async with pass_or_acquire_connection(get_asyncpg_engine(app), connection) as conn:
        result = await conn.stream(access_rights_query)
        return {row.project_uuid: row.access_rights async for row in result}
