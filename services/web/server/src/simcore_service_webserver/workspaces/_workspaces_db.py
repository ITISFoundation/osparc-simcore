""" Database API

    - Adds a layer to the postgres API with a focus on the projects comments

"""

import logging
from typing import cast

from aiohttp import web
from models_library.products import ProductName
from models_library.rest_ordering import OrderBy, OrderDirection
from models_library.users import GroupID, UserID
from models_library.workspaces import (
    UserWorkspaceAccessRightsDB,
    WorkspaceDB,
    WorkspaceID,
)
from pydantic import NonNegativeInt
from simcore_postgres_database.models.groups import user_to_groups
from simcore_postgres_database.models.workspaces import workspaces
from simcore_postgres_database.models.workspaces_access_rights import (
    workspaces_access_rights,
)
from sqlalchemy import asc, desc, func
from sqlalchemy.dialects.postgresql import BOOLEAN, INTEGER
from sqlalchemy.sql import Subquery, select

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
        return WorkspaceDB.model_validate(row)


access_rights_subquery = (
    select(
        workspaces_access_rights.c.workspace_id,
        func.jsonb_object_agg(
            workspaces_access_rights.c.gid,
            func.jsonb_build_object(
                "read",
                workspaces_access_rights.c.read,
                "write",
                workspaces_access_rights.c.write,
                "delete",
                workspaces_access_rights.c.delete,
            ),
        )
        .filter(
            workspaces_access_rights.c.read  # Filters out entries where "read" is False
        )
        .label("access_rights"),
    ).group_by(workspaces_access_rights.c.workspace_id)
).subquery("access_rights_subquery")


def _create_my_access_rights_subquery(user_id: UserID) -> Subquery:
    return (
        select(
            workspaces_access_rights.c.workspace_id,
            func.json_build_object(
                "read",
                func.max(workspaces_access_rights.c.read.cast(INTEGER)).cast(BOOLEAN),
                "write",
                func.max(workspaces_access_rights.c.write.cast(INTEGER)).cast(BOOLEAN),
                "delete",
                func.max(workspaces_access_rights.c.delete.cast(INTEGER)).cast(BOOLEAN),
            ).label("my_access_rights"),
        )
        .select_from(
            workspaces_access_rights.join(
                user_to_groups, user_to_groups.c.gid == workspaces_access_rights.c.gid
            )
        )
        .where(user_to_groups.c.uid == user_id)
        .group_by(workspaces_access_rights.c.workspace_id)
    ).subquery("my_access_rights_subquery")


async def list_workspaces_for_user(
    app: web.Application,
    *,
    user_id: UserID,
    product_name: ProductName,
    offset: NonNegativeInt,
    limit: NonNegativeInt,
    order_by: OrderBy,
) -> tuple[int, list[UserWorkspaceAccessRightsDB]]:
    my_access_rights_subquery = _create_my_access_rights_subquery(user_id=user_id)

    base_query = (
        select(
            *_SELECTION_ARGS,
            access_rights_subquery.c.access_rights,
            my_access_rights_subquery.c.my_access_rights,
        )
        .select_from(
            workspaces.join(access_rights_subquery).join(my_access_rights_subquery)
        )
        .where(workspaces.c.product_name == product_name)
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
        results: list[UserWorkspaceAccessRightsDB] = [
            UserWorkspaceAccessRightsDB.model_validate(row) for row in rows
        ]

        return cast(int, total_count), results


async def get_workspace_for_user(
    app: web.Application,
    user_id: UserID,
    workspace_id: WorkspaceID,
    product_name: ProductName,
) -> UserWorkspaceAccessRightsDB:
    my_access_rights_subquery = _create_my_access_rights_subquery(user_id=user_id)

    base_query = (
        select(
            *_SELECTION_ARGS,
            access_rights_subquery.c.access_rights,
            my_access_rights_subquery.c.my_access_rights,
        )
        .select_from(
            workspaces.join(access_rights_subquery).join(my_access_rights_subquery)
        )
        .where(
            (workspaces.c.workspace_id == workspace_id)
            & (workspaces.c.product_name == product_name)
        )
    )

    async with get_database_engine(app).acquire() as conn:
        result = await conn.execute(base_query)
        row = await result.first()
        if row is None:
            raise WorkspaceAccessForbiddenError(
                reason=f"User {user_id} does not have access to the workspace {workspace_id}. Or workspace does not exist.",
            )
        return UserWorkspaceAccessRightsDB.model_validate(row)


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
        return WorkspaceDB.model_validate(row)


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
