""" Database API

    - Adds a layer to the postgres API with a focus on the projects comments

"""

import logging
from typing import cast

from aiohttp import web
from models_library.products import ProductName
from models_library.rest_ordering import OrderBy, OrderDirection
from models_library.users import GroupID, UserID
from models_library.workspaces import UserWorkspaceDB, WorkspaceDB, WorkspaceID
from pydantic import NonNegativeInt
from simcore_postgres_database.models.groups import user_to_groups
from simcore_postgres_database.models.workspaces import workspaces
from simcore_postgres_database.models.workspaces_access_rights import (
    workspaces_access_rights,
)
from sqlalchemy import asc, desc, func
from sqlalchemy.dialects.postgresql import BOOLEAN, INTEGER
from sqlalchemy.sql import select

from ..db.plugin import get_database_engine
from .errors import WorkspaceAccessForbiddenError, WorkspaceNotFoundError

_logger = logging.getLogger(__name__)


_SELECTION_ARGS = (
    workspaces.c.workspace_id,
    workspaces.c.name,
    workspaces.c.description,
    workspaces.c.owner_primary_gid,
    workspaces.c.thumbnail,
    workspaces.c.created,
    workspaces.c.modified,
)


async def create_workspace(
    app: web.Application,
    product_name: ProductName,
    owner_primary_gid: GroupID,
    name: str,
    description: str | None,
    thumbnail: str | None,
) -> WorkspaceDB:
    async with get_database_engine(app).acquire() as conn:
        result = await conn.execute(
            workspaces.insert()
            .values(
                name=name,
                description=description,
                owner_primary_gid=owner_primary_gid,
                thumbnail=thumbnail,
                created=func.now(),
                modified=func.now(),
                product_name=product_name,
            )
            .returning(*_SELECTION_ARGS)
        )
        row = await result.first()
        return WorkspaceDB.from_orm(row)


_SELECTION_ARGS_WITH_USER_ACCESS_RIGHTS = (
    _SELECTION_ARGS,
    func.max(workspaces_access_rights.c.read.cast(INTEGER)).cast(BOOLEAN).label("read"),
    func.max(workspaces_access_rights.c.write.cast(INTEGER))
    .cast(BOOLEAN)
    .label("write"),
    func.max(workspaces_access_rights.c.delete.cast(INTEGER))
    .cast(BOOLEAN)
    .label("delete"),
)

_JOIN_TABLES = user_to_groups.join(
    workspaces_access_rights, user_to_groups.c.gid == workspaces_access_rights.c.gid
).join(workspaces, workspaces_access_rights.c.workspace_id == workspaces.c.workspace_id)


async def list_workspaces_for_user(
    app: web.Application,
    *,
    user_id: UserID,
    product_name: ProductName,
    offset: NonNegativeInt,
    limit: NonNegativeInt,
    order_by: OrderBy,
) -> tuple[int, list[UserWorkspaceDB]]:
    base_query = (
        select(*_SELECTION_ARGS_WITH_USER_ACCESS_RIGHTS)
        .select_from(_JOIN_TABLES)
        .where(
            (user_to_groups.c.uid == user_id)
            & (user_to_groups.c.access_rights["read"].astext == "true")
            & (workspaces.c.product_name == product_name)
        )
        .group_by(_SELECTION_ARGS)
    )

    # Select total count from base_query
    subquery = base_query.subquery()
    count_query = select(func.count()).select_from(subquery)

    # Ordering and pagination
    if order_by.direction == OrderDirection.ASC:
        list_query = base_query.order_by(asc(getattr(workspaces.c, order_by.field)))
    else:
        list_query = base_query.order_by(desc(getattr(workspaces.c, order_by.field)))
    list_query = list_query.offset(offset).limit(limit)

    async with get_database_engine(app).acquire() as conn:
        count_result = await conn.execute(count_query)
        total_count = await count_result.scalar()

        result = await conn.execute(list_query)
        rows = await result.fetchall() or []
        results: list[UserWorkspaceDB] = [UserWorkspaceDB.from_orm(row) for row in rows]

        return cast(int, total_count), results


async def get_workspace_for_user(
    app: web.Application,
    user_id: UserID,
    workspace_id: WorkspaceID,
    product_name: ProductName,
) -> UserWorkspaceDB:
    stmt = (
        select(*_SELECTION_ARGS_WITH_USER_ACCESS_RIGHTS)
        .select_from(_JOIN_TABLES)
        .where(
            (user_to_groups.c.uid == user_id)
            & (user_to_groups.c.access_rights["read"].astext == "true")
            & (workspaces.c.workspace_id == workspace_id)
            & (workspaces.c.product_name == product_name)
        )
        .group_by(_SELECTION_ARGS)
    )

    async with get_database_engine(app).acquire() as conn:
        result = await conn.execute(stmt)
        row = await result.first()
        if row is None:
            raise WorkspaceAccessForbiddenError(
                reason=f"User does not have access to the workspace {workspace_id}. Or workspace does not exist.",
            )
        return UserWorkspaceDB.from_orm(row)


async def update_workspace(
    app: web.Application,
    workspace_id: WorkspaceID,
    name: str,
    description: str | None,
    thumbnail: str | None,
    product_name: ProductName,
) -> WorkspaceDB:
    async with get_database_engine(app).acquire() as conn:
        result = await conn.execute(
            workspaces.update()
            .values(
                name=name,
                description=description,
                thumbnail=thumbnail,
                modified=func.now(),
            )
            .where(
                (workspaces.c.workspace_id == workspace_id)
                & (workspaces.c.product_name == product_name)
            )
            .returning(*_SELECTION_ARGS)
        )
        row = await result.first()
        if row is None:
            raise WorkspaceNotFoundError(reason=f"Workspace {workspace_id} not found.")
        return WorkspaceDB.from_orm(row)


async def delete_workspace(
    app: web.Application,
    workspace_id: WorkspaceID,
    product_name: ProductName,
) -> None:
    async with get_database_engine(app).acquire() as conn:
        await conn.execute(
            workspaces.delete().where(
                (workspaces.c.workspace_id == workspace_id)
                & (workspaces.c.product_name == product_name)
            )
        )
