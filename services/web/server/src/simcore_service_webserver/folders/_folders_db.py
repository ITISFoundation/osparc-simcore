""" Database API

    - Adds a layer to the postgres API with a focus on the projects comments

"""

import logging
from typing import cast

from aiohttp import web
from models_library.folders import FolderDB, FolderID
from models_library.products import ProductName
from models_library.rest_ordering import OrderBy, OrderDirection
from models_library.users import GroupID, UserID
from models_library.workspaces import WorkspaceID
from pydantic import NonNegativeInt, parse_obj_as
from simcore_postgres_database.models.folders_v2 import folders_v2
from sqlalchemy import func
from sqlalchemy.sql import asc, desc, select

from ..db.plugin import get_database_engine
from .errors import FolderAccessForbiddenError, FolderNotFoundError

_logger = logging.getLogger(__name__)


_SELECTION_ARGS = (
    folders_v2.c.folder_id,
    folders_v2.c.name,
    folders_v2.c.parent_folder_id,
    folders_v2.c.created_by_gid,
    folders_v2.c.created,
    folders_v2.c.modified,
    folders_v2.c.user_id,
    folders_v2.c.workspace_id,
)


async def create_folder(
    app: web.Application,
    product_name: ProductName,
    created_by_gid: GroupID,
    folder_name: str,
    parent_folder_id: FolderID | None,
    user_id: UserID | None,
    workspace_id: WorkspaceID | None,
) -> FolderDB:
    assert not (
        user_id is not None and workspace_id is not None
    ), "Both user_id and workspace_id cannot be provided at the same time. Please provide only one."

    async with get_database_engine(app).acquire() as conn:
        result = await conn.execute(
            folders_v2.insert()
            .values(
                name=folder_name,
                parent_folder_id=parent_folder_id,
                product_name=product_name,
                user_id=user_id,
                workspace_id=workspace_id,
                created_by_gid=created_by_gid,
                created=func.now(),
                modified=func.now(),
            )
            .returning(_SELECTION_ARGS)
        )
        row = await result.first()
        return parse_obj_as(FolderDB, row)


async def list_folders(
    app: web.Application,
    *,
    content_of_folder_id: FolderID | None,
    user_id: UserID | None,
    workspace_id: WorkspaceID | None,
    product_name: ProductName,
    offset: NonNegativeInt,
    limit: int,
    order_by: OrderBy,
) -> tuple[int, list[FolderDB]]:
    """
    content_of_folder_id - Used to filter in which folder we want to list folders. None means root folder.
    """

    assert not (
        user_id is not None and workspace_id is not None
    ), "Both user_id and workspace_id cannot be provided at the same time. Please provide only one."

    base_query = (
        select(*_SELECTION_ARGS)
        .select_from(folders_v2)
        .where(
            (folders_v2.c.product_name == product_name)
            & (folders_v2.c.parent_folder_id == content_of_folder_id)
        )
    )

    if user_id:
        base_query = base_query.where(folders_v2.c.user_id == user_id)
    else:
        assert workspace_id  # nosec
        base_query = base_query.where(folders_v2.c.workspace_id == workspace_id)

    # Select total count from base_query
    subquery = base_query.subquery()
    count_query = select(func.count()).select_from(subquery)

    # Ordering and pagination
    if order_by.direction == OrderDirection.ASC:
        list_query = base_query.order_by(asc(getattr(folders_v2.c, order_by.field)))
    else:
        list_query = base_query.order_by(desc(getattr(folders_v2.c, order_by.field)))
    list_query = list_query.offset(offset).limit(limit)

    async with get_database_engine(app).acquire() as conn:
        count_result = await conn.execute(count_query)
        total_count = await count_result.scalar()

        result = await conn.execute(list_query)
        rows = await result.fetchall() or []
        results: list[FolderDB] = [parse_obj_as(FolderDB, row) for row in rows]
        return cast(int, total_count), results


async def get_folder_db(
    app: web.Application,
    folder_id: FolderID,
    product_name: ProductName,
) -> FolderDB:
    query = (
        select(*_SELECTION_ARGS)
        .select_from(folders_v2)
        .where(
            (folders_v2.c.product_name == product_name)
            & (folders_v2.c.folder_id == folder_id)
        )
    )

    async with get_database_engine(app).acquire() as conn:
        result = await conn.execute(query)
        row = await result.first()
        if row is None:
            raise FolderAccessForbiddenError(
                reason=f"Folder {folder_id} does not exist.",
            )
        return parse_obj_as(FolderDB, row)


async def get_folder_for_user_or_workspace(
    app: web.Application,
    folder_id: FolderID,
    product_name: ProductName,
    user_id: UserID | None,
    workspace_id: WorkspaceID | None,
) -> FolderDB:
    assert not (
        user_id is not None and workspace_id is not None
    ), "Both user_id and workspace_id cannot be provided at the same time. Please provide only one."

    query = (
        select(*_SELECTION_ARGS)
        .select_from(folders_v2)
        .where(
            (folders_v2.c.product_name == product_name)
            & (folders_v2.c.folder_id == folder_id)
        )
    )

    if user_id:
        query = query.where(folders_v2.c.user_id == user_id)
    else:
        query = query.where(folders_v2.c.workspace_id == workspace_id)

    async with get_database_engine(app).acquire() as conn:
        result = await conn.execute(query)
        row = await result.first()
        if row is None:
            raise FolderAccessForbiddenError(
                reason=f"User does not have access to the folder {folder_id}. Or folder does not exist.",
            )
        return parse_obj_as(FolderDB, row)


# async def check_user_access_to_folder(
#     app: web.Application,
#     folder_id: FolderID,
#     product_name: ProductName,
# ) -> bool:
#     query = (
#         select(*_SELECTION_ARGS)
#         .select_from(folders_v2.join(user_to_groups))
#         .where(
#             (folders_v2.c.product_name == product_name)
#             & (folders_v2.c.folder_id == folder_id)
#         )
#     )

#     stmt = (
#         select(*_SELECTION_ARGS_WITH_USER_ACCESS_RIGHTS)
#         .select_from(_JOIN_TABLES)
#         .where(
#             (user_to_groups.c.uid == user_id)
#             & (user_to_groups.c.access_rights["read"].astext == "true")
#             & (workspaces.c.workspace_id == workspace_id)
#             & (workspaces.c.product_name == product_name)
#         )
#         .group_by(_SELECTION_ARGS)
#     )

#     async with get_database_engine(app).acquire() as conn:
#         result = await conn.execute(query)
#         row = await result.first()
#         if row is None:
#             raise FolderAccessForbiddenError(
#                 reason=f"User does not have access to the folder {folder_id}. Or folder does not exist.",
#             )
#         return parse_obj_as(FolderDB, row)


async def update_folder(
    app: web.Application,
    folder_id: FolderID,
    name: str,
    parent_folder_id: FolderID | None,
    product_name: ProductName,
) -> FolderDB:
    async with get_database_engine(app).acquire() as conn:
        result = await conn.execute(
            folders_v2.update()
            .values(
                name=name,
                parent_folder_id=parent_folder_id,
                modified=func.now(),
            )
            .where(
                (folders_v2.c.folder_id == folder_id)
                & (folders_v2.c.product_name == product_name)
            )
            .returning(*_SELECTION_ARGS)
        )
        row = await result.first()
        if row is None:
            raise FolderNotFoundError(reason=f"Folder {folder_id} not found.")
        return parse_obj_as(FolderDB, row)


async def delete_folder(
    app: web.Application,
    folder_id: FolderID,
    product_name: ProductName,
) -> None:
    async with get_database_engine(app).acquire() as conn:
        await conn.execute(
            folders_v2.delete().where(
                (folders_v2.c.folder_id == folder_id)
                & (folders_v2.c.product_name == product_name)
            )
        )
