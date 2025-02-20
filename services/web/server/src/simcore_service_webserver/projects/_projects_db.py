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
from pydantic import NonNegativeInt, PositiveInt
from simcore_postgres_database.models.projects import projects
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

_logger = logging.getLogger(__name__)


PROJECT_DB_COLS = get_columns_from_db_model(
    # NOTE: MD: I intentionally didn't include the workbench. There is a special interface
    # for the workbench, and at some point, this column should be removed from the table.
    # The same holds true for access_rights/ui/classifiers/quality, but we have decided to proceed step by step.
    projects,
    ProjectDBGet,
)

_OLDEST_TRASHED_FIRST = OrderBy(field=IDStr("trashed"), direction=OrderDirection.ASC)


def _to_sql_expression(table: sa.Table, order_by: OrderBy):
    direction_func: Callable = {
        OrderDirection.ASC: sql.asc,
        OrderDirection.DESC: sql.desc,
    }[order_by.direction]
    return direction_func(table.columns[order_by.field])


async def list_trashed_projects(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    # filter
    trashed_explicitly: bool | UnSet = UnSet.VALUE,
    trashed_before: datetime | UnSet = UnSet.VALUE,
    # pagination
    offset: NonNegativeInt = 0,
    limit: PositiveInt = MAXIMUM_NUMBER_OF_ITEMS_PER_PAGE,
    # order
    order_by: OrderBy = _OLDEST_TRASHED_FIRST,
) -> tuple[int, list[ProjectDBGet]]:

    base_query = sql.select(PROJECT_DB_COLS).where(projects.c.trashed.is_not(None))

    if is_set(trashed_explicitly):
        assert isinstance(trashed_explicitly, bool)  # nosec
        base_query = base_query.where(
            projects.c.trashed_explicitly.is_(trashed_explicitly)
        )

    if is_set(trashed_before):
        assert isinstance(trashed_before, datetime)  # nosec
        base_query = base_query.where(projects.c.trashed < trashed_before)

    # Select total count from base_query
    count_query = sql.select(sql.func.count()).select_from(base_query.subquery())

    # Ordering and pagination
    list_query = (
        base_query.order_by(_to_sql_expression(projects, order_by))
        .offset(offset)
        .limit(limit)
    )

    async with pass_or_acquire_connection(get_asyncpg_engine(app), connection) as conn:
        total_count = await conn.scalar(count_query)

        result = await conn.stream(list_query)
        projects_list: list[ProjectDBGet] = [
            ProjectDBGet.model_validate(row) async for row in result
        ]
        return cast(int, total_count), projects_list


async def get_project(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    project_uuid: ProjectID,
) -> ProjectDBGet:
    async with pass_or_acquire_connection(get_asyncpg_engine(app), connection) as conn:
        query = sql.select(*PROJECT_DB_COLS).where(projects.c.uuid == f"{project_uuid}")
        result = await conn.execute(query)
        row = result.one_or_none()
        if row is None:
            raise ProjectNotFoundError(project_uuid=project_uuid)
        return ProjectDBGet.model_validate(row)


def _select_trashed_by_primary_gid_query() -> sql.Select:
    return sql.select(
        projects.c.uuid,
        users.c.primary_gid.label("trashed_by_primary_gid"),
    ).select_from(projects.outerjoin(users, projects.c.trashed_by == users.c.id))


async def get_trashed_by_primary_gid(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    projects_uuid: ProjectID,
) -> GroupID | None:
    query = _select_trashed_by_primary_gid_query().where(
        projects.c.uuid == projects_uuid
    )

    async with pass_or_acquire_connection(get_asyncpg_engine(app), connection) as conn:
        result = await conn.execute(query)
        row = result.first()
        return row.trashed_by_primary_gid if row else None


async def batch_get_trashed_by_primary_gid(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    projects_uuids: list[ProjectID],
) -> list[GroupID | None]:
    """Batch version of get_trashed_by_primary_gid

    Returns:
        values of trashed_by_primary_gid in the SAME ORDER as projects_uuids
    """
    if not projects_uuids:
        return []

    projects_uuids_str = [f"{uuid}" for uuid in projects_uuids]

    query = (
        _select_trashed_by_primary_gid_query().where(
            projects.c.uuid.in_(projects_uuids_str)
        )
    ).order_by(
        # Preserves the order of folders_ids
        # SEE https://docs.sqlalchemy.org/en/20/core/sqlelement.html#sqlalchemy.sql.expression.case
        sql.case(
            {
                project_uuid: index
                for index, project_uuid in enumerate(projects_uuids_str)
            },
            value=projects.c.uuid,
        )
    )
    async with pass_or_acquire_connection(get_asyncpg_engine(app), connection) as conn:
        result = await conn.stream(query)
        rows = {row.uuid: row.trashed_by_primary_gid async for row in result}

    return [rows.get(uuid) for uuid in projects_uuids_str]


async def patch_project(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    project_uuid: ProjectID,
    new_partial_project_data: dict,
) -> ProjectDBGet:
    async with transaction_context(get_asyncpg_engine(app), connection) as conn:
        result = await conn.stream(
            projects.update()
            .values(
                **new_partial_project_data,
                last_change_date=sql.func.now(),
            )
            .where(projects.c.uuid == f"{project_uuid}")
            .returning(*PROJECT_DB_COLS)
        )
        row = await result.one_or_none()
        if row is None:
            raise ProjectNotFoundError(project_uuid=project_uuid)
        return ProjectDBGet.model_validate(row)


async def delete_project(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    project_uuid: ProjectID,
) -> ProjectDBGet:
    async with transaction_context(get_asyncpg_engine(app), connection) as conn:
        result = await conn.stream(
            projects.delete()
            .where(projects.c.uuid == f"{project_uuid}")
            .returning(*PROJECT_DB_COLS)
        )
        row = await result.one_or_none()
        if row is None:
            raise ProjectNotFoundError(project_uuid=project_uuid)
        return ProjectDBGet.model_validate(row)
