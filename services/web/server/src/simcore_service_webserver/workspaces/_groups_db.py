""" Database API

    - Adds a layer to the postgres API with a focus on the projects comments

"""

import logging
from datetime import datetime

from aiohttp import web
from models_library.users import GroupID
from models_library.workspaces import WorkspaceID
from pydantic import BaseModel, ConfigDict
from simcore_postgres_database.models.workspaces_access_rights import (
    workspaces_access_rights,
)
from simcore_postgres_database.utils_repos import (
    pass_or_acquire_connection,
    transaction_context,
)
from sqlalchemy import func, literal_column
from sqlalchemy.ext.asyncio import AsyncConnection
from sqlalchemy.sql import select

from ..db.plugin import get_asyncpg_engine
from .errors import WorkspaceGroupNotFoundError

_logger = logging.getLogger(__name__)

### Models


class WorkspaceGroupGetDB(BaseModel):
    gid: GroupID
    read: bool
    write: bool
    delete: bool
    created: datetime
    modified: datetime
    model_config = ConfigDict(from_attributes=True)


## DB API


async def create_workspace_group(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    workspace_id: WorkspaceID,
    group_id: GroupID,
    read: bool,
    write: bool,
    delete: bool,
) -> WorkspaceGroupGetDB:
    async with transaction_context(get_asyncpg_engine(app), connection) as conn:
        result = await conn.stream(
            workspaces_access_rights.insert()
            .values(
                workspace_id=workspace_id,
                gid=group_id,
                read=read,
                write=write,
                delete=delete,
                created=func.now(),
                modified=func.now(),
            )
            .returning(literal_column("*"))
        )
        row = await result.first()
        return WorkspaceGroupGetDB.model_validate(row)


async def list_workspace_groups(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    workspace_id: WorkspaceID,
) -> list[WorkspaceGroupGetDB]:
    stmt = (
        select(
            workspaces_access_rights.c.gid,
            workspaces_access_rights.c.read,
            workspaces_access_rights.c.write,
            workspaces_access_rights.c.delete,
            workspaces_access_rights.c.created,
            workspaces_access_rights.c.modified,
        )
        .select_from(workspaces_access_rights)
        .where(workspaces_access_rights.c.workspace_id == workspace_id)
    )

    async with pass_or_acquire_connection(get_asyncpg_engine(app), connection) as conn:
        result = await conn.stream(stmt)
        return [WorkspaceGroupGetDB.model_validate(row) async for row in result]


async def get_workspace_group(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    workspace_id: WorkspaceID,
    group_id: GroupID,
) -> WorkspaceGroupGetDB:
    stmt = (
        select(
            workspaces_access_rights.c.gid,
            workspaces_access_rights.c.read,
            workspaces_access_rights.c.write,
            workspaces_access_rights.c.delete,
            workspaces_access_rights.c.created,
            workspaces_access_rights.c.modified,
        )
        .select_from(workspaces_access_rights)
        .where(
            (workspaces_access_rights.c.workspace_id == workspace_id)
            & (workspaces_access_rights.c.gid == group_id)
        )
    )

    async with pass_or_acquire_connection(get_asyncpg_engine(app), connection) as conn:
        result = await conn.stream(stmt)
        row = await result.first()
        if row is None:
            raise WorkspaceGroupNotFoundError(
                workspace_id=workspace_id, group_id=group_id
            )
        return WorkspaceGroupGetDB.model_validate(row)


async def update_workspace_group(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    workspace_id: WorkspaceID,
    group_id: GroupID,
    read: bool,
    write: bool,
    delete: bool,
) -> WorkspaceGroupGetDB:
    async with transaction_context(get_asyncpg_engine(app), connection) as conn:
        result = await conn.stream(
            workspaces_access_rights.update()
            .values(
                read=read,
                write=write,
                delete=delete,
            )
            .where(
                (workspaces_access_rights.c.workspace_id == workspace_id)
                & (workspaces_access_rights.c.gid == group_id)
            )
            .returning(literal_column("*"))
        )
        row = await result.first()
        if row is None:
            raise WorkspaceGroupNotFoundError(
                workspace_id=workspace_id, group_id=group_id
            )
        return WorkspaceGroupGetDB.model_validate(row)


async def delete_workspace_group(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    workspace_id: WorkspaceID,
    group_id: GroupID,
) -> None:
    async with transaction_context(get_asyncpg_engine(app), connection) as conn:
        await conn.execute(
            workspaces_access_rights.delete().where(
                (workspaces_access_rights.c.workspace_id == workspace_id)
                & (workspaces_access_rights.c.gid == group_id)
            )
        )
