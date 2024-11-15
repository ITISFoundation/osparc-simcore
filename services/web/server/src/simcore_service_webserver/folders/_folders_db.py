""" Database API

    - Adds a layer to the postgres API with a focus on the projects comments

"""

import logging
from datetime import datetime
from typing import Any, Final, cast

import sqlalchemy as sa
from aiohttp import web
from models_library.folders import (
    FolderDB,
    FolderID,
    FolderQuery,
    FolderScope,
    UserFolderAccessRightsDB,
)
from models_library.products import ProductName
from models_library.projects import ProjectID
from models_library.rest_ordering import OrderBy, OrderDirection
from models_library.users import GroupID, UserID
from models_library.workspaces import WorkspaceID, WorkspaceQuery, WorkspaceScope
from pydantic import NonNegativeInt
from simcore_postgres_database.models.folders_v2 import folders_v2
from simcore_postgres_database.models.projects import projects
from simcore_postgres_database.models.projects_to_folders import projects_to_folders
from simcore_postgres_database.utils_repos import (
    pass_or_acquire_connection,
    transaction_context,
)
from simcore_postgres_database.utils_workspaces_sql import (
    create_my_workspace_access_rights_subquery,
)
from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncConnection
from sqlalchemy.orm import aliased
from sqlalchemy.sql import ColumnElement, CompoundSelect, Select, asc, desc, select

from ..db.plugin import get_asyncpg_engine
from .errors import FolderAccessForbiddenError, FolderNotFoundError

_logger = logging.getLogger(__name__)


class UnSet:
    ...


_unset: Final = UnSet()


def as_dict_exclude_unset(**params) -> dict[str, Any]:
    return {k: v for k, v in params.items() if not isinstance(v, UnSet)}


_SELECTION_ARGS = (
    folders_v2.c.folder_id,
    folders_v2.c.name,
    folders_v2.c.parent_folder_id,
    folders_v2.c.created_by_gid,
    folders_v2.c.created,
    folders_v2.c.modified,
    folders_v2.c.trashed_at,
    folders_v2.c.user_id,
    folders_v2.c.workspace_id,
)


async def create(
    app: web.Application,
    connection: AsyncConnection | None = None,
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

    async with transaction_context(get_asyncpg_engine(app), connection) as conn:
        result = await conn.stream(
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
        return FolderDB.model_validate(row)


async def list_(  # pylint: disable=too-many-arguments,too-many-branches
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    product_name: ProductName,
    user_id: UserID,
    # hierarchy filters
    folder_query: FolderQuery,
    workspace_query: WorkspaceQuery,
    # attribute filters
    filter_trashed: bool | None,
    filter_by_text: str | None,
    # pagination
    offset: NonNegativeInt,
    limit: int,
    # order
    order_by: OrderBy,
) -> tuple[int, list[UserFolderAccessRightsDB]]:
    """
    folder_query - Used to filter in which folder we want to list folders.
    trashed - If set to true, it returns folders **explicitly** trashed, if false then non-trashed folders.
    """

    workspace_access_rights_subquery = create_my_workspace_access_rights_subquery(
        user_id=user_id
    )

    if workspace_query.workspace_scope is not WorkspaceScope.SHARED:
        assert workspace_query.workspace_scope in (  # nosec
            WorkspaceScope.PRIVATE,
            WorkspaceScope.ALL,
        )

        private_workspace_query = (
            select(
                *_SELECTION_ARGS,
                func.json_build_object(
                    "read",
                    sa.text("true"),
                    "write",
                    sa.text("true"),
                    "delete",
                    sa.text("true"),
                ).label("my_access_rights"),
            )
            .select_from(folders_v2)
            .where(
                (folders_v2.c.product_name == product_name)
                & (folders_v2.c.user_id == user_id)
            )
        )
    else:
        private_workspace_query = None

    if workspace_query.workspace_scope is not WorkspaceScope.PRIVATE:
        assert workspace_query.workspace_scope in (  # nosec
            WorkspaceScope.SHARED,
            WorkspaceScope.ALL,
        )

        shared_workspace_query = (
            select(
                *_SELECTION_ARGS, workspace_access_rights_subquery.c.my_access_rights
            )
            .select_from(
                folders_v2.join(
                    workspace_access_rights_subquery,
                    folders_v2.c.workspace_id
                    == workspace_access_rights_subquery.c.workspace_id,
                )
            )
            .where(
                (folders_v2.c.product_name == product_name)
                & (folders_v2.c.user_id.is_(None))
            )
        )

        if workspace_query.workspace_scope == WorkspaceScope.SHARED:
            shared_workspace_query = shared_workspace_query.where(
                folders_v2.c.workspace_id == workspace_query.workspace_id
            )

    else:
        shared_workspace_query = None

    attributes_filters: list[ColumnElement] = []

    if filter_trashed is not None:
        attributes_filters.append(
            (
                (folders_v2.c.trashed_at.is_not(None))
                & (folders_v2.c.trashed_explicitly.is_(True))
            )
            if filter_trashed
            else folders_v2.c.trashed_at.is_(None)
        )
    if folder_query.folder_scope is not FolderScope.ALL:
        if folder_query.folder_scope == FolderScope.SPECIFIC:
            attributes_filters.append(
                folders_v2.c.parent_folder_id == folder_query.folder_id
            )
        else:
            assert folder_query.folder_scope == FolderScope.ROOT  # nosec
            attributes_filters.append(folders_v2.c.parent_folder_id.is_(None))
    if filter_by_text:
        attributes_filters.append(folders_v2.c.name.ilike(f"%{filter_by_text}%"))

    ###
    # Combined
    ###

    combined_query: CompoundSelect | Select | None = None
    if private_workspace_query is not None and shared_workspace_query is not None:
        combined_query = sa.union_all(
            private_workspace_query.where(sa.and_(*attributes_filters)),
            shared_workspace_query.where(sa.and_(*attributes_filters)),
        )
    elif private_workspace_query is not None:
        combined_query = private_workspace_query.where(sa.and_(*attributes_filters))
    elif shared_workspace_query is not None:
        combined_query = shared_workspace_query.where(sa.and_(*attributes_filters))

    if combined_query is None:
        msg = f"No valid queries were provided to combine. Workspace scope: {workspace_query.workspace_scope}"
        raise ValueError(msg)

    # Select total count from base_query
    count_query = select(func.count()).select_from(combined_query.subquery())

    # Ordering and pagination
    if order_by.direction == OrderDirection.ASC:
        list_query = combined_query.order_by(asc(getattr(folders_v2.c, order_by.field)))
    else:
        list_query = combined_query.order_by(
            desc(getattr(folders_v2.c, order_by.field))
        )
    list_query = list_query.offset(offset).limit(limit)

    async with pass_or_acquire_connection(get_asyncpg_engine(app), connection) as conn:
        total_count = await conn.scalar(count_query)

        result = await conn.stream(list_query)
        folders: list[UserFolderAccessRightsDB] = [
            UserFolderAccessRightsDB.model_validate(row) async for row in result
        ]
        return cast(int, total_count), folders


async def get(
    app: web.Application,
    connection: AsyncConnection | None = None,
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

    async with pass_or_acquire_connection(get_asyncpg_engine(app), connection) as conn:
        result = await conn.stream(query)
        row = await result.first()
        if row is None:
            raise FolderAccessForbiddenError(
                reason=f"Folder {folder_id} does not exist.",
            )
        return FolderDB.model_validate(row)


async def get_for_user_or_workspace(
    app: web.Application,
    connection: AsyncConnection | None = None,
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

    async with pass_or_acquire_connection(get_asyncpg_engine(app), connection) as conn:
        result = await conn.stream(query)
        row = await result.first()
        if row is None:
            raise FolderAccessForbiddenError(
                reason=f"User does not have access to the folder {folder_id}. Or folder does not exist.",
            )
        return FolderDB.model_validate(row)


async def update(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    folders_id_or_ids: FolderID | set[FolderID],
    product_name: ProductName,
    # updatable columns
    name: str | UnSet = _unset,
    parent_folder_id: FolderID | None | UnSet = _unset,
    trashed_at: datetime | None | UnSet = _unset,
    trashed_explicitly: bool | UnSet = _unset,
) -> FolderDB:
    """
    Batch/single patch of folder/s
    """
    # NOTE: exclude unset can also be done using a pydantic model and dict(exclude_unset=True)
    updated = as_dict_exclude_unset(
        name=name,
        parent_folder_id=parent_folder_id,
        trashed_at=trashed_at,
        trashed_explicitly=trashed_explicitly,
    )

    query = (
        (folders_v2.update().values(modified=func.now(), **updated))
        .where(folders_v2.c.product_name == product_name)
        .returning(*_SELECTION_ARGS)
    )

    if isinstance(folders_id_or_ids, set):
        # batch-update
        query = query.where(folders_v2.c.folder_id.in_(list(folders_id_or_ids)))
    else:
        # single-update
        query = query.where(folders_v2.c.folder_id == folders_id_or_ids)

    async with transaction_context(get_asyncpg_engine(app), connection) as conn:
        result = await conn.stream(query)
        row = await result.first()
        if row is None:
            raise FolderNotFoundError(reason=f"Folder {folders_id_or_ids} not found.")
        return FolderDB.model_validate(row)


async def delete_recursively(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    folder_id: FolderID,
    product_name: ProductName,
) -> None:
    async with transaction_context(get_asyncpg_engine(app), connection) as conn:
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
        result = await conn.stream(final_query)
        # list of tuples [(folder_id, parent_folder_id), ...] ex. [(1, None), (2, 1)]
        rows = [row async for row in result]

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
    connection: AsyncConnection | None = None,
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

    async with pass_or_acquire_connection(get_asyncpg_engine(app), connection) as conn:

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
        result = await conn.stream(final_query)
        # list of tuples [(folder_id, parent_folder_id), ...] ex. [(1, None), (2, 1)]
        folder_ids = [item[0] async for item in result]

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

        result = await conn.stream(query)
        return [ProjectID(row[0]) async for row in result]


async def get_folders_recursively(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    folder_id: FolderID,
    product_name: ProductName,
) -> list[FolderID]:
    async with pass_or_acquire_connection(get_asyncpg_engine(app), connection) as conn:

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
        result = await conn.stream(final_query)
        return [FolderID(row[0]) async for row in result]
