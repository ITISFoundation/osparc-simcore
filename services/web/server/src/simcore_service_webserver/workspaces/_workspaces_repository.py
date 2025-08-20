import logging
from datetime import datetime
from typing import cast

from aiohttp import web
from common_library.exclude import Unset, is_set
from models_library.groups import GroupID
from models_library.products import ProductName
from models_library.rest_ordering import OrderBy, OrderDirection
from models_library.users import UserID
from models_library.workspaces import (
    UserWorkspaceWithAccessRights,
    Workspace,
    WorkspaceID,
    WorkspaceUpdates,
)
from pydantic import NonNegativeInt
from simcore_postgres_database.models.users import users
from simcore_postgres_database.models.workspaces import workspaces
from simcore_postgres_database.models.workspaces_access_rights import (
    workspaces_access_rights,
)
from simcore_postgres_database.utils_repos import (
    pass_or_acquire_connection,
    transaction_context,
)
from simcore_postgres_database.utils_workspaces_sql import (
    create_my_workspace_access_rights_subquery,
)
from sqlalchemy import asc, desc, func
from sqlalchemy.ext.asyncio import AsyncConnection
from sqlalchemy.sql import Select, select

from ..db.plugin import get_asyncpg_engine
from ._workspaces_models import WorkspaceDBGet
from .errors import WorkspaceAccessForbiddenError, WorkspaceNotFoundError

_logger = logging.getLogger(__name__)


_WORKSPACE_SELECTION_COLS = (
    workspaces.c.workspace_id,
    workspaces.c.name,
    workspaces.c.description,
    workspaces.c.owner_primary_gid,
    workspaces.c.thumbnail,
    workspaces.c.created,
    workspaces.c.modified,
    workspaces.c.trashed,
    workspaces.c.trashed_by,
    workspaces.c.product_name,
)


async def create_workspace(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    product_name: ProductName,
    owner_primary_gid: GroupID,
    name: str,
    description: str | None,
    thumbnail: str | None,
) -> Workspace:
    async with transaction_context(get_asyncpg_engine(app), connection) as conn:
        result = await conn.stream(
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
            .returning(*_WORKSPACE_SELECTION_COLS)
        )
        row = await result.first()
        return Workspace.model_validate(row)


def _create_base_select_query(
    caller_user_id: UserID, product_name: ProductName
) -> Select:
    # any other access
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

    # caller's access rights
    my_access_rights_subquery = create_my_workspace_access_rights_subquery(
        user_id=caller_user_id
    )

    return (
        select(
            *_WORKSPACE_SELECTION_COLS,
            access_rights_subquery.c.access_rights,
            my_access_rights_subquery.c.my_access_rights,
            users.c.primary_gid.label("trashed_by_primary_gid"),
        )
        .select_from(
            workspaces.join(access_rights_subquery)
            .join(my_access_rights_subquery)
            .outerjoin(users, workspaces.c.trashed_by == users.c.id)
        )
        .where(workspaces.c.product_name == product_name)
    )


async def list_workspaces_for_user(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    user_id: UserID,
    product_name: ProductName,
    filter_trashed: bool | None,
    filter_by_text: str | None,
    offset: NonNegativeInt,
    limit: NonNegativeInt,
    order_by: OrderBy,
) -> tuple[int, list[UserWorkspaceWithAccessRights]]:
    base_select_query = _create_base_select_query(
        caller_user_id=user_id, product_name=product_name
    )

    if filter_trashed is not None:
        base_select_query = base_select_query.where(
            workspaces.c.trashed.is_not(None)
            if filter_trashed
            else workspaces.c.trashed.is_(None)
        )
    if filter_by_text is not None:
        base_select_query = base_select_query.where(
            (workspaces.c.name.ilike(f"%{filter_by_text}%"))
            | (workspaces.c.description.ilike(f"%{filter_by_text}%"))
        )

    # Select total count from base_query
    count_query = select(func.count()).select_from(base_select_query.subquery())

    # Ordering and pagination
    if order_by.direction == OrderDirection.ASC:
        list_query = base_select_query.order_by(
            asc(getattr(workspaces.c, order_by.field))
        )
    else:
        list_query = base_select_query.order_by(
            desc(getattr(workspaces.c, order_by.field))
        )
    list_query = list_query.offset(offset).limit(limit)

    async with pass_or_acquire_connection(get_asyncpg_engine(app), connection) as conn:
        total_count = await conn.scalar(count_query)

        result = await conn.stream(list_query)
        items: list[UserWorkspaceWithAccessRights] = [
            UserWorkspaceWithAccessRights.model_validate(row) async for row in result
        ]

        return cast(int, total_count), items


async def get_workspace_for_user(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    user_id: UserID,
    workspace_id: WorkspaceID,
    product_name: ProductName,
) -> UserWorkspaceWithAccessRights:
    select_query = _create_base_select_query(
        caller_user_id=user_id, product_name=product_name
    ).where(workspaces.c.workspace_id == workspace_id)

    async with pass_or_acquire_connection(get_asyncpg_engine(app), connection) as conn:
        result = await conn.execute(select_query)
        row = result.one_or_none()
        if row is None:
            raise WorkspaceAccessForbiddenError(
                details=f"User {user_id} does not have access to the workspace {workspace_id}. Or workspace does not exist.",
            )
        return UserWorkspaceWithAccessRights.model_validate(row)


async def get_workspace_db_get(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    workspace_id: WorkspaceID,
) -> WorkspaceDBGet:
    async with pass_or_acquire_connection(get_asyncpg_engine(app), connection) as conn:
        result = await conn.execute(
            select(
                *_WORKSPACE_SELECTION_COLS,
            )
            .select_from(workspaces)
            .where(workspaces.c.workspace_id == workspace_id)
        )
        row = result.one_or_none()
        if row is None:
            raise WorkspaceNotFoundError(details=f"Workspace {workspace_id} not found.")
    return WorkspaceDBGet.model_validate(row)


async def update_workspace(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    product_name: ProductName,
    workspace_id: WorkspaceID,
    updates: WorkspaceUpdates,
) -> Workspace:
    # NOTE: at least 'touch' if updated_values is empty
    _updates = {
        **updates.model_dump(exclude_unset=True),
        "modified": func.now(),
    }

    async with transaction_context(get_asyncpg_engine(app), connection) as conn:
        result = await conn.stream(
            workspaces.update()
            .values(**_updates)
            .where(
                (workspaces.c.workspace_id == workspace_id)
                & (workspaces.c.product_name == product_name)
            )
            .returning(*_WORKSPACE_SELECTION_COLS)
        )
        row = await result.first()
        if row is None:
            raise WorkspaceNotFoundError(details=f"Workspace {workspace_id} not found.")
        return Workspace.model_validate(row)


async def delete_workspace(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    workspace_id: WorkspaceID,
    product_name: ProductName,
) -> None:
    async with transaction_context(get_asyncpg_engine(app), connection) as conn:
        await conn.execute(
            workspaces.delete().where(
                (workspaces.c.workspace_id == workspace_id)
                & (workspaces.c.product_name == product_name)
            )
        )


assert set(WorkspaceDBGet.model_fields.keys()) == {
    col.name for col in _WORKSPACE_SELECTION_COLS
}


async def list_workspaces_db_get_as_admin(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    # filter
    trashed_before: datetime | Unset = Unset.VALUE,
    # pagination
    offset: NonNegativeInt,
    limit: int,
    # ordering
    order_by: OrderBy,
) -> tuple[int, list[WorkspaceDBGet]]:
    """
    NOTE: This is an internal function used for administrative purposes.
    Ex. It lists trashed workspaces across the application for cleanup tasks.
    """
    base_query = select(*_WORKSPACE_SELECTION_COLS).where(
        workspaces.c.trashed.is_not(None)
    )

    if is_set(trashed_before):
        assert isinstance(trashed_before, datetime)  # nosec
        base_query = base_query.where(workspaces.c.trashed < trashed_before)

    # Select total count from base_query
    count_query = select(func.count()).select_from(base_query.subquery())

    # Ordering and pagination
    if order_by.direction == OrderDirection.ASC:
        list_query = base_query.order_by(
            asc(getattr(workspaces.c, order_by.field)), workspaces.c.workspace_id
        )
    else:
        list_query = base_query.order_by(
            desc(getattr(workspaces.c, order_by.field)), workspaces.c.workspace_id
        )
    list_query = list_query.offset(offset).limit(limit)

    async with pass_or_acquire_connection(get_asyncpg_engine(app), connection) as conn:
        total_count = await conn.scalar(count_query)

        result = await conn.stream(list_query)
        workspaces_list: list[WorkspaceDBGet] = [
            WorkspaceDBGet.model_validate(row) async for row in result
        ]
        return cast(int, total_count), workspaces_list
