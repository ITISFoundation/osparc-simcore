import logging
from collections.abc import Callable
from datetime import datetime
from typing import cast

import sqlalchemy as sa
from aiohttp import web
from common_library.exclude import Unset, as_dict_exclude_unset, is_set
from models_library.folders import (
    FolderDB,
    FolderID,
    FolderQuery,
    FolderScope,
    UserFolder,
)
from models_library.groups import GroupID
from models_library.products import ProductName
from models_library.projects import ProjectID
from models_library.rest_ordering import OrderBy, OrderDirection
from models_library.users import UserID
from models_library.workspaces import WorkspaceID, WorkspaceQuery, WorkspaceScope
from pydantic import NonNegativeInt
from simcore_postgres_database.models.folders_v2 import folders_v2
from simcore_postgres_database.models.projects import projects
from simcore_postgres_database.models.projects_to_folders import projects_to_folders
from simcore_postgres_database.models.users import users
from simcore_postgres_database.utils_repos import (
    get_columns_from_db_model,
    pass_or_acquire_connection,
    transaction_context,
)
from simcore_postgres_database.utils_workspaces_sql import (
    create_my_workspace_access_rights_subquery,
)
from sqlalchemy import sql
from sqlalchemy.ext.asyncio import AsyncConnection
from sqlalchemy.orm import aliased
from sqlalchemy.sql import ColumnElement, CompoundSelect, Select

from ..db.plugin import get_asyncpg_engine
from .errors import FolderAccessForbiddenError, FolderNotFoundError

_logger = logging.getLogger(__name__)


_FOLDER_DB_MODEL_COLS = get_columns_from_db_model(folders_v2, FolderDB)


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
                created=sql.func.now(),
                modified=sql.func.now(),
            )
            .returning(*_FOLDER_DB_MODEL_COLS)
        )
        row = await result.first()
        return FolderDB.model_validate(row)


def _create_private_workspace_query(
    product_name: ProductName,
    user_id: UserID,
    workspace_scope: WorkspaceScope,
):
    if workspace_scope is not WorkspaceScope.SHARED:
        assert workspace_scope in (  # nosec
            WorkspaceScope.PRIVATE,
            WorkspaceScope.ALL,
        )
        return (
            sql.select(
                *_FOLDER_DB_MODEL_COLS,
                sql.func.json_build_object(
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
    return None


def _create_shared_workspace_query(
    product_name: ProductName,
    user_id: UserID,
    workspace_scope: WorkspaceScope,
    workspace_id: WorkspaceID | None,
):
    if workspace_scope is not WorkspaceScope.PRIVATE:
        assert workspace_scope in (  # nosec
            WorkspaceScope.SHARED,
            WorkspaceScope.ALL,
        )

        workspace_access_rights_subquery = create_my_workspace_access_rights_subquery(
            user_id=user_id
        )

        shared_workspace_query = (
            sql.select(
                *_FOLDER_DB_MODEL_COLS,
                workspace_access_rights_subquery.c.my_access_rights,
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

        if workspace_scope == WorkspaceScope.SHARED:
            shared_workspace_query = shared_workspace_query.where(
                folders_v2.c.workspace_id == workspace_id
            )

    else:
        shared_workspace_query = None

    return shared_workspace_query


def _to_expression(order_by: OrderBy):
    direction_func: Callable = {
        OrderDirection.ASC: sql.asc,
        OrderDirection.DESC: sql.desc,
    }[order_by.direction]
    return direction_func(folders_v2.columns[order_by.field])


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
) -> tuple[int, list[UserFolder]]:
    """
    folder_query - Used to filter in which folder we want to list folders.
    trashed - If set to true, it returns folders **explicitly** trashed, if false then non-trashed folders.
    """

    private_workspace_query = _create_private_workspace_query(
        workspace_scope=workspace_query.workspace_scope,
        product_name=product_name,
        user_id=user_id,
    )
    shared_workspace_query = _create_shared_workspace_query(
        workspace_scope=workspace_query.workspace_scope,
        product_name=product_name,
        user_id=user_id,
        workspace_id=workspace_query.workspace_id,
    )

    attributes_filters: list[ColumnElement] = []

    if filter_trashed is not None:
        attributes_filters.append(
            (
                (folders_v2.c.trashed.is_not(None))
                & (folders_v2.c.trashed_explicitly.is_(True))
            )
            if filter_trashed
            else folders_v2.c.trashed.is_(None)
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
    count_query = sql.select(sql.func.count()).select_from(combined_query.subquery())

    # Ordering and pagination
    list_query = (
        combined_query.order_by(_to_expression(order_by), folders_v2.c.folder_id)
        .offset(offset)
        .limit(limit)
    )

    async with pass_or_acquire_connection(get_asyncpg_engine(app), connection) as conn:
        total_count = await conn.scalar(count_query)

        result = await conn.stream(list_query)
        folders: list[UserFolder] = [
            UserFolder.model_validate(row) async for row in result
        ]
        return cast(int, total_count), folders


async def list_folders_db_as_admin(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    # filter
    trashed_explicitly: bool | Unset = Unset.VALUE,
    trashed_before: datetime | Unset = Unset.VALUE,
    shared_workspace_id: WorkspaceID | Unset = Unset.VALUE,  # <-- Workspace filter
    # pagination
    offset: NonNegativeInt,
    limit: int,
    # order
    order_by: OrderBy,
) -> tuple[int, list[FolderDB]]:
    """
    NOTE: this is app-wide i.e. no product, user or workspace filtered
    """
    base_query = sql.select(*_FOLDER_DB_MODEL_COLS)

    if is_set(trashed_explicitly):
        assert isinstance(trashed_explicitly, bool)  # nosec
        base_query = base_query.where(
            (folders_v2.c.trashed_explicitly.is_(trashed_explicitly))
            & (folders_v2.c.trashed.is_not(None))
        )

    if is_set(trashed_before):
        assert isinstance(trashed_before, datetime)  # nosec
        base_query = base_query.where(
            (folders_v2.c.trashed < trashed_before)
            & (folders_v2.c.trashed.is_not(None))
        )

    if is_set(shared_workspace_id):
        assert isinstance(shared_workspace_id, int)  # nosec
        base_query = base_query.where(folders_v2.c.workspace_id == shared_workspace_id)

    # Select total count from base_query
    count_query = sql.select(sql.func.count()).select_from(base_query.subquery())

    # Ordering and pagination
    list_query = (
        base_query.order_by(_to_expression(order_by), folders_v2.c.folder_id)
        .offset(offset)
        .limit(limit)
    )

    async with pass_or_acquire_connection(get_asyncpg_engine(app), connection) as conn:
        total_count = await conn.scalar(count_query)

        result = await conn.stream(list_query)
        folders: list[FolderDB] = [FolderDB.model_validate(row) async for row in result]
        return cast(int, total_count), folders


def _create_base_select_query(folder_id: FolderID, product_name: ProductName) -> Select:
    return sql.select(
        *_FOLDER_DB_MODEL_COLS,
    ).where(
        (folders_v2.c.product_name == product_name)
        & (folders_v2.c.folder_id == folder_id)
    )


async def get(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    folder_id: FolderID,
    product_name: ProductName,
) -> FolderDB:
    query = _create_base_select_query(folder_id=folder_id, product_name=product_name)

    async with pass_or_acquire_connection(get_asyncpg_engine(app), connection) as conn:
        result = await conn.execute(query)
        row = result.first()
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
    user_id: UserID | None,  # owned
    workspace_id: WorkspaceID | None,
) -> FolderDB:
    assert not (
        user_id is not None and workspace_id is not None
    ), "Both user_id and workspace_id cannot be provided at the same time. Please provide only one."

    query = _create_base_select_query(folder_id=folder_id, product_name=product_name)

    if user_id:
        # ownership
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
    # pylint: disable=too-many-arguments
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    folders_id_or_ids: FolderID | set[FolderID],
    product_name: ProductName,
    # updatable columns
    name: str | Unset = Unset.VALUE,
    parent_folder_id: FolderID | None | Unset = Unset.VALUE,
    trashed: datetime | None | Unset = Unset.VALUE,
    trashed_explicitly: bool | Unset = Unset.VALUE,
    trashed_by: UserID | None | Unset = Unset.VALUE,  # who trashed
    workspace_id: WorkspaceID | None | Unset = Unset.VALUE,
    user_id: UserID | None | Unset = Unset.VALUE,  # ownership
) -> FolderDB:
    """
    Batch/single patch of folder/s
    """
    # NOTE: exclude unset can also be done using a pydantic model and model_dump(exclude_unset=True)
    updated = as_dict_exclude_unset(
        name=name,
        parent_folder_id=parent_folder_id,
        trashed=trashed,
        trashed_by=trashed_by,  # (who trashed)
        trashed_explicitly=trashed_explicitly,
        workspace_id=workspace_id,
        user_id=user_id,  # (who owns)
    )

    query = (
        (folders_v2.update().values(modified=sql.func.now(), **updated))
        .where(folders_v2.c.product_name == product_name)
        .returning(*_FOLDER_DB_MODEL_COLS)
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
        base_query = sql.select(
            folders_v2.c.folder_id, folders_v2.c.parent_folder_id
        ).where(
            (folders_v2.c.folder_id == folder_id)  # <-- specified folder id
            & (folders_v2.c.product_name == product_name)
        )
        folder_hierarchy_cte = base_query.cte(name="folder_hierarchy", recursive=True)

        # Step 2: Define the recursive case
        folder_alias = aliased(folders_v2)
        recursive_query = sql.select(
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
        final_query = sql.select(folder_hierarchy_cte)
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
        base_query = sql.select(
            folders_v2.c.folder_id, folders_v2.c.parent_folder_id
        ).where(
            (folders_v2.c.folder_id == folder_id)  # <-- specified folder id
            & (folders_v2.c.product_name == product_name)
        )
        folder_hierarchy_cte = base_query.cte(name="folder_hierarchy", recursive=True)

        # Step 2: Define the recursive case
        folder_alias = aliased(folders_v2)
        recursive_query = sql.select(
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
        final_query = sql.select(folder_hierarchy_cte)
        result = await conn.stream(final_query)
        # list of tuples [(folder_id, parent_folder_id), ...] ex. [(1, None), (2, 1)]
        folder_ids = [item[0] async for item in result]

        query = (
            sql.select(projects_to_folders.c.project_uuid)
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


async def get_all_folders_and_projects_ids_recursively(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    folder_id: FolderID,
    private_workspace_user_id_or_none: UserID | None,
    product_name: ProductName,
) -> tuple[list[FolderID], list[ProjectID]]:
    """
    The purpose of this function is to retrieve all subfolders and projects within the provided folder ID.
    """

    async with pass_or_acquire_connection(get_asyncpg_engine(app), connection) as conn:

        # Step 1: Define the base case for the recursive CTE
        base_query = sql.select(
            folders_v2.c.folder_id, folders_v2.c.parent_folder_id
        ).where(
            (folders_v2.c.folder_id == folder_id)  # <-- specified folder id
            & (folders_v2.c.product_name == product_name)
        )
        folder_hierarchy_cte = base_query.cte(name="folder_hierarchy", recursive=True)

        # Step 2: Define the recursive case
        folder_alias = aliased(folders_v2)
        recursive_query = sql.select(
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
        final_query = sql.select(folder_hierarchy_cte)
        result = await conn.stream(final_query)
        # list of tuples [(folder_id, parent_folder_id), ...] ex. [(1, None), (2, 1)]
        folder_ids = [item.folder_id async for item in result]

        query = sql.select(projects_to_folders.c.project_uuid).where(
            (projects_to_folders.c.folder_id.in_(folder_ids))
            & (projects_to_folders.c.user_id == private_workspace_user_id_or_none)
        )

        result = await conn.stream(query)
        project_ids = [ProjectID(row.project_uuid) async for row in result]

        return folder_ids, project_ids


async def get_folders_recursively(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    folder_id: FolderID,
    product_name: ProductName,
) -> list[FolderID]:
    async with pass_or_acquire_connection(get_asyncpg_engine(app), connection) as conn:

        # Step 1: Define the base case for the recursive CTE
        base_query = sql.select(
            folders_v2.c.folder_id, folders_v2.c.parent_folder_id
        ).where(
            (folders_v2.c.folder_id == folder_id)  # <-- specified folder id
            & (folders_v2.c.product_name == product_name)
        )
        folder_hierarchy_cte = base_query.cte(name="folder_hierarchy", recursive=True)

        # Step 2: Define the recursive case
        folder_alias = aliased(folders_v2)
        recursive_query = sql.select(
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
        final_query = sql.select(folder_hierarchy_cte)
        result = await conn.stream(final_query)
        return cast(list[FolderID], [row.folder_id async for row in result])


def _select_trashed_by_primary_gid_query():
    return sa.sql.select(
        folders_v2.c.folder_id,
        users.c.primary_gid.label("trashed_by_primary_gid"),
    ).select_from(
        folders_v2.outerjoin(users, folders_v2.c.trashed_by == users.c.id),
    )


async def get_trashed_by_primary_gid(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    folder_id: FolderID,
) -> GroupID | None:
    query = _select_trashed_by_primary_gid_query().where(
        folders_v2.c.folder_id == folder_id
    )

    async with pass_or_acquire_connection(get_asyncpg_engine(app), connection) as conn:
        result = await conn.execute(query)
        row = result.one_or_none()
        return row.trashed_by_primary_gid if row else None


async def batch_get_trashed_by_primary_gid(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    folders_ids: list[FolderID],
) -> list[GroupID | None]:
    if not folders_ids:
        return []

    query = (
        _select_trashed_by_primary_gid_query().where(
            folders_v2.c.folder_id.in_(folders_ids)
        )
    ).order_by(
        # Preserves the order of folders_ids
        # SEE https://docs.sqlalchemy.org/en/20/core/sqlelement.html#sqlalchemy.sql.expression.case
        sa.case(
            {folder_id: index for index, folder_id in enumerate(folders_ids)},
            value=folders_v2.c.folder_id,
        )
    )

    async with pass_or_acquire_connection(get_asyncpg_engine(app), connection) as conn:
        result = await conn.stream(query)
        rows = {row.folder_id: row.trashed_by_primary_gid async for row in result}

    return [rows.get(folder_id) for folder_id in folders_ids]
