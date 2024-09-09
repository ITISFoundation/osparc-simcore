""" Database API

    - Adds a layer to the postgres API with a focus on the projects comments

"""

import logging
from typing import cast

from aiohttp import web
from models_library.folders import FolderDB, FolderID
from models_library.products import ProductName
from models_library.projects import ProjectID
from models_library.rest_ordering import OrderBy, OrderDirection
from models_library.users import GroupID, UserID
from models_library.workspaces import WorkspaceID
from pydantic import NonNegativeInt
from simcore_postgres_database.models.folders_v2 import folders_v2
from simcore_postgres_database.models.projects import projects
from simcore_postgres_database.models.projects_to_folders import projects_to_folders
from sqlalchemy import func
from sqlalchemy.orm import aliased
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


async def create(
    app: web.Application,
    *,
    created_by_gid: GroupID,
    folder_name: str,
    product_name: ProductName,
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
            .returning(*_SELECTION_ARGS)
        )
        row = await result.first()
        return FolderDB.from_orm(row)


async def list_(
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
        results: list[FolderDB] = [FolderDB.from_orm(row) for row in rows]
        return cast(int, total_count), results


async def get(
    app: web.Application,
    *,
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
        return FolderDB.from_orm(row)


async def get_for_user_or_workspace(
    app: web.Application,
    *,
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
        return FolderDB.from_orm(row)


async def update(
    app: web.Application,
    *,
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
        return FolderDB.from_orm(row)


async def delete_recursively(
    app: web.Application,
    *,
    folder_id: FolderID,
    product_name: ProductName,
) -> None:
    async with get_database_engine(app).acquire() as conn, conn.begin():
        # Step 1: Define the base case for the recursive CTE
        base_query = select(
            folders_v2.c.folder_id, folders_v2.c.parent_folder_id
        ).where(
            (folders_v2.c.folder_id == folder_id)  # <-- specified folder id
            & (folders_v2.c.product_name == product_name)
        )
        folder_hierarchy_cte = base_query.cte(name="folder_hierarchy", recursive=True)
        # Step 2: Define the recursive case
        folder_alias = aliased(folders_v2)
        recursive_query = select(
            folder_alias.c.folder_id, folder_alias.c.parent_folder_id
        ).select_from(
            folder_alias.join(
                folder_hierarchy_cte,
                folder_alias.c.parent_folder_id == folder_hierarchy_cte.c.folder_id,
            )
        )
        # Step 3: Combine base and recursive cases into a CTE
        folder_hierarchy_cte = folder_hierarchy_cte.union_all(recursive_query)
        # Step 4: Execute the query to get all descendants
        final_query = select(folder_hierarchy_cte)
        result = await conn.execute(final_query)
        rows = (  # list of tuples [(folder_id, parent_folder_id), ...] ex. [(1, None), (2, 1)]
            await result.fetchall() or []
        )

        # Sort folders so that child folders come first
        sorted_folders = sorted(
            rows, key=lambda x: (x[1] is not None, x[1]), reverse=True
        )
        folder_ids = [item[0] for item in sorted_folders]
        await conn.execute(
            folders_v2.delete().where(folders_v2.c.folder_id.in_(folder_ids))
        )


async def get_projects_recursively_only_if_user_is_owner(
    app: web.Application,
    *,
    folder_id: FolderID,
    private_workspace_user_id_or_none: UserID | None,
    user_id: UserID,
    product_name: ProductName,
) -> list[ProjectID]:
    """
    The purpose of this function is to retrieve all projects within the provided folder ID.
    These projects are subsequently deleted, so we only return projects where the user is the owner.
    For future improvement, we can return all projects for which the user has delete permissions.
    This permission check would require using the `workspace_access_rights` table for workspace projects,
    or the `users_to_groups` table for private workspace projects.
    """

    async with get_database_engine(app).acquire() as conn, conn.begin():
        # Step 1: Define the base case for the recursive CTE
        base_query = select(
            folders_v2.c.folder_id, folders_v2.c.parent_folder_id
        ).where(
            (folders_v2.c.folder_id == folder_id)  # <-- specified folder id
            & (folders_v2.c.product_name == product_name)
        )
        folder_hierarchy_cte = base_query.cte(name="folder_hierarchy", recursive=True)
        # Step 2: Define the recursive case
        folder_alias = aliased(folders_v2)
        recursive_query = select(
            folder_alias.c.folder_id, folder_alias.c.parent_folder_id
        ).select_from(
            folder_alias.join(
                folder_hierarchy_cte,
                folder_alias.c.parent_folder_id == folder_hierarchy_cte.c.folder_id,
            )
        )
        # Step 3: Combine base and recursive cases into a CTE
        folder_hierarchy_cte = folder_hierarchy_cte.union_all(recursive_query)
        # Step 4: Execute the query to get all descendants
        final_query = select(folder_hierarchy_cte)
        result = await conn.execute(final_query)
        rows = (  # list of tuples [(folder_id, parent_folder_id), ...] ex. [(1, None), (2, 1)]
            await result.fetchall() or []
        )

        folder_ids = [item[0] for item in rows]

        query = (
            select(projects_to_folders.c.project_uuid)
            .join(projects)
            .where(
                (projects_to_folders.c.folder_id.in_(folder_ids))
                & (projects_to_folders.c.user_id == private_workspace_user_id_or_none)
            )
        )
        if private_workspace_user_id_or_none is not None:
            query = query.where(projects.c.prj_owner == user_id)

        result = await conn.execute(query)

        rows = await result.fetchall() or []
        results = [ProjectID(row[0]) for row in rows]
        return results
