import logging
from collections.abc import Callable, Iterable
from datetime import datetime
from typing import cast

import sqlalchemy as sa
from aiohttp import web
from common_library.exclude import Unset, is_set
from models_library.basic_types import IDStr
from models_library.groups import GroupID
from models_library.products import ProductName
from models_library.projects import ProjectID
from models_library.rest_ordering import OrderBy, OrderDirection
from models_library.rest_pagination import MAXIMUM_NUMBER_OF_ITEMS_PER_PAGE
from models_library.workspaces import WorkspaceID
from pydantic import NonNegativeInt, PositiveInt, TypeAdapter
from simcore_postgres_database.models.projects import projects
from simcore_postgres_database.models.projects_to_products import projects_to_products
from simcore_postgres_database.models.users import users
from simcore_postgres_database.utils_projects_nodes import make_workbench_subquery
from simcore_postgres_database.utils_repos import (
    get_columns_from_db_model,
    pass_or_acquire_connection,
    transaction_context,
)
from sqlalchemy import sql
from sqlalchemy.ext.asyncio import AsyncConnection

from ..db.plugin import get_asyncpg_engine
from .exceptions import ProjectNotFoundError
from .models import ProjectDBGet, ProjectWithWorkbenchDBGet

_logger = logging.getLogger(__name__)


PROJECT_DB_COLS = get_columns_from_db_model(
    # NOTE: MD: I intentionally didn't include the workbench. There is a special interface
    # for the workbench, and at some point, this column should be removed from the table.
    # The same holds true for access_rights/ui/classifiers/quality, but we have decided to proceed step by step.
    projects,
    ProjectDBGet,
)

OLDEST_TRASHED_FIRST = OrderBy(field=IDStr("trashed"), direction=OrderDirection.ASC)


def _to_sql_expression(table: sa.Table, order_by: OrderBy):
    direction_func: Callable = {
        OrderDirection.ASC: sql.asc,
        OrderDirection.DESC: sql.desc,
    }[order_by.direction]
    return direction_func(table.columns[order_by.field])


async def list_projects_db_get_as_admin(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    # filter
    trashed_explicitly: bool | Unset = Unset.VALUE,
    trashed_before: datetime | Unset = Unset.VALUE,
    shared_workspace_id: WorkspaceID | Unset = Unset.VALUE,
    # pagination
    offset: NonNegativeInt = 0,
    limit: PositiveInt = MAXIMUM_NUMBER_OF_ITEMS_PER_PAGE,
    # order
    order_by: OrderBy,
) -> tuple[int, list[ProjectDBGet]]:

    base_query = sql.select(*PROJECT_DB_COLS).where(projects.c.trashed.is_not(None))

    if is_set(trashed_explicitly):
        assert isinstance(trashed_explicitly, bool)  # nosec
        base_query = base_query.where(
            projects.c.trashed_explicitly.is_(trashed_explicitly)
        )

    if is_set(trashed_before):
        assert isinstance(trashed_before, datetime)  # nosec
        base_query = base_query.where(projects.c.trashed < trashed_before)

    if is_set(shared_workspace_id):
        assert isinstance(shared_workspace_id, int)  # nosec
        base_query = base_query.where(projects.c.workspace_id == shared_workspace_id)

    # Select total count from base_query
    count_query = sql.select(sql.func.count()).select_from(base_query.subquery())

    # Ordering and pagination
    list_query = (
        base_query.order_by(_to_sql_expression(projects, order_by), projects.c.id)
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
        result = await conn.execute(
            sa.select(*PROJECT_DB_COLS).where(projects.c.uuid == f"{project_uuid}")
        )
        row = result.one_or_none()
        if row is None:
            raise ProjectNotFoundError(project_uuid=project_uuid)
        return ProjectDBGet.model_validate(row)


async def get_project_product(
    app,
    connection: AsyncConnection | None = None,
    *,
    project_uuid: ProjectID,
) -> ProductName:
    async with pass_or_acquire_connection(get_asyncpg_engine(app), connection) as conn:
        result = await conn.scalar(
            sa.select(projects_to_products.c.product_name).where(
                projects_to_products.c.project_uuid == f"{project_uuid}"
            )
        )
        if result is None:
            raise ProjectNotFoundError(project_uuid=project_uuid)
        return TypeAdapter(ProductName).validate_python(result)


async def get_project_with_workbench(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    project_uuid: ProjectID,
) -> ProjectWithWorkbenchDBGet:
    async with pass_or_acquire_connection(get_asyncpg_engine(app), connection) as conn:
        workbench_subquery = make_workbench_subquery()
        query = (
            sql.select(
                *PROJECT_DB_COLS,
                sa.func.coalesce(
                    workbench_subquery.c.workbench, sa.text("'{}'::json")
                ).label("workbench"),
            )
            .select_from(
                projects.outerjoin(
                    workbench_subquery,
                    projects.c.uuid == workbench_subquery.c.project_uuid,
                )
            )
            .where(projects.c.uuid == f"{project_uuid}")
        )
        result = await conn.execute(query)
        row = result.one_or_none()
        if row is None:
            raise ProjectNotFoundError(project_uuid=project_uuid)
        return ProjectWithWorkbenchDBGet.model_validate(row)


async def batch_get_project_name(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    projects_uuids: list[ProjectID],
) -> list[str | None]:
    if not projects_uuids:
        return []

    projects_uuids_str = [f"{uuid}" for uuid in projects_uuids]

    query = (
        sql.select(
            projects.c.uuid,
            projects.c.name,
        )
        .select_from(projects)
        .where(projects.c.uuid.in_(projects_uuids_str))
    ).order_by(
        # Preserves the order of projects_uuids
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
        rows = {row.uuid: row.name async for row in result}

    return [rows.get(project_uuid) for project_uuid in projects_uuids_str]


async def batch_get_projects(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    project_uuids: Iterable[ProjectID],
) -> dict[ProjectID, ProjectDBGet]:
    if not project_uuids:
        return {}
    async with pass_or_acquire_connection(get_asyncpg_engine(app), connection) as conn:
        query = (
            sql.select(projects)
            .select_from(projects)
            .where(projects.c.uuid.in_([f"{uuid}" for uuid in project_uuids]))
        )
        result = await conn.stream(query)
        return {
            ProjectID(row.uuid): ProjectDBGet.model_validate(row)
            async for row in result
        }


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
        projects.c.uuid == f"{projects_uuid}"
    )

    async with pass_or_acquire_connection(get_asyncpg_engine(app), connection) as conn:
        result = await conn.execute(query)
        row = result.one_or_none()
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
        # Preserves the order of project_uuids
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

    return [rows.get(project_uuid) for project_uuid in projects_uuids_str]


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
