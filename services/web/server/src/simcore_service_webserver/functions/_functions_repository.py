# pylint: disable=too-many-arguments


import sqlalchemy
from aiohttp import web
from models_library.basic_types import IDStr
from models_library.functions import (
    FunctionClass,
    FunctionID,
    FunctionInputs,
    FunctionInputSchema,
    FunctionOutputSchema,
    FunctionsApiAccessRights,
    FunctionUpdate,
    RegisteredFunctionDB,
)
from models_library.functions_errors import (
    FunctionHasJobsCannotDeleteError,
    FunctionIDNotFoundError,
)
from models_library.products import ProductName
from models_library.rest_ordering import OrderBy, OrderDirection
from models_library.rest_pagination import PageMetaInfoLimitOffset
from models_library.users import UserID
from simcore_postgres_database.models.funcapi_function_jobs_table import (
    function_jobs_table,
)
from simcore_postgres_database.models.funcapi_functions_access_rights_table import (
    functions_access_rights_table,
)
from simcore_postgres_database.models.funcapi_functions_table import functions_table
from simcore_postgres_database.utils_repos import (
    pass_or_acquire_connection,
    transaction_context,
)
from sqlalchemy import String, cast
from sqlalchemy.ext.asyncio import AsyncConnection
from sqlalchemy.sql import ColumnElement, func

from ..db.plugin import get_asyncpg_engine
from ..groups.api import list_all_user_groups_ids
from ..users import users_service
from ._functions_permissions_repository import (
    _internal_set_group_permissions,
    check_user_api_access_rights,
    check_user_permissions,
)
from ._functions_table_cols import (
    _FUNCTIONS_TABLE_COLS,
)

DEFAULT_ORDER_BY = OrderBy(field=IDStr("modified"), direction=OrderDirection.DESC)


async def create_function(  # noqa: PLR0913
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    user_id: UserID,
    product_name: ProductName,
    function_class: FunctionClass,
    class_specific_data: dict,
    title: str,
    description: str,
    input_schema: FunctionInputSchema,
    output_schema: FunctionOutputSchema,
    default_inputs: FunctionInputs,
) -> RegisteredFunctionDB:
    async with transaction_context(get_asyncpg_engine(app), connection) as transaction:
        await check_user_api_access_rights(
            app,
            connection=transaction,
            user_id=user_id,
            product_name=product_name,
            api_access_rights=[FunctionsApiAccessRights.WRITE_FUNCTIONS],
        )

        result = await transaction.execute(
            functions_table.insert()
            .values(
                title=title,
                description=description,
                input_schema=(input_schema.model_dump()),
                output_schema=(output_schema.model_dump()),
                function_class=function_class,
                class_specific_data=class_specific_data,
                default_inputs=default_inputs,
            )
            .returning(*_FUNCTIONS_TABLE_COLS)
        )
        row = result.one()

        registered_function = RegisteredFunctionDB.model_validate(row)

        user_primary_group_id = await users_service.get_user_primary_group_id(app, user_id=user_id)
        await _internal_set_group_permissions(
            app,
            connection=transaction,
            permission_group_id=user_primary_group_id,
            product_name=product_name,
            object_type="function",
            object_ids=[registered_function.uuid],
            read=True,
            write=True,
            execute=True,
        )

    return RegisteredFunctionDB.model_validate(row)


async def get_function(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    user_id: UserID,
    product_name: ProductName,
    function_id: FunctionID,
) -> RegisteredFunctionDB:
    async with pass_or_acquire_connection(get_asyncpg_engine(app), connection) as conn:
        await check_user_permissions(
            app,
            connection=conn,
            user_id=user_id,
            product_name=product_name,
            object_id=function_id,
            object_type="function",
            permissions=["read"],
        )

        result = await conn.execute(functions_table.select().where(functions_table.c.uuid == function_id))
        row = result.one_or_none()

        if row is None:
            raise FunctionIDNotFoundError(function_id=function_id)
        return RegisteredFunctionDB.model_validate(row)


def _create_list_functions_attributes_filters(
    *,
    filter_by_function_class: FunctionClass | None,
    search_by_multi_columns: str | None,
    search_by_function_title: str | None,
) -> list[ColumnElement]:
    attributes_filters: list[ColumnElement] = []

    if filter_by_function_class is not None:
        attributes_filters.append(functions_table.c.function_class == filter_by_function_class.value)

    if search_by_multi_columns is not None:
        attributes_filters.append(
            (functions_table.c.title.ilike(f"%{search_by_multi_columns}%"))
            | (functions_table.c.description.ilike(f"%{search_by_multi_columns}%"))
            | (cast(functions_table.c.uuid, String).ilike(f"%{search_by_multi_columns}%"))
        )

    if search_by_function_title is not None:
        attributes_filters.append(functions_table.c.title.ilike(f"%{search_by_function_title}%"))

    return attributes_filters


async def list_functions(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    user_id: UserID,
    product_name: ProductName,
    pagination_limit: int,
    pagination_offset: int,
    order_by: OrderBy | None = None,
    filter_by_function_class: FunctionClass | None = None,
    search_by_multi_columns: str | None = None,
    search_by_function_title: str | None = None,
) -> tuple[list[RegisteredFunctionDB], PageMetaInfoLimitOffset]:
    async with pass_or_acquire_connection(get_asyncpg_engine(app), connection) as conn:
        await check_user_api_access_rights(
            app,
            connection=conn,
            user_id=user_id,
            product_name=product_name,
            api_access_rights=[FunctionsApiAccessRights.READ_FUNCTIONS],
        )
        user_groups = await list_all_user_groups_ids(app, user_id=user_id)
        attributes_filters = _create_list_functions_attributes_filters(
            filter_by_function_class=filter_by_function_class,
            search_by_multi_columns=search_by_multi_columns,
            search_by_function_title=search_by_function_title,
        )

        # Use GROUP BY on the primary key to ensure unique functions
        base_query = (
            functions_table.select()
            .join(
                functions_access_rights_table,
                functions_table.c.uuid == functions_access_rights_table.c.function_uuid,
            )
            .where(
                functions_access_rights_table.c.group_id.in_(user_groups),
                functions_access_rights_table.c.product_name == product_name,
                functions_access_rights_table.c.read,
                *attributes_filters,
            )
            .group_by(functions_table.c.uuid)
        )

        # Get total count
        total_count = await conn.scalar(func.count().select().select_from(base_query.subquery()))
        if total_count == 0:
            return [], PageMetaInfoLimitOffset(total=0, offset=pagination_offset, limit=pagination_limit, count=0)

        if order_by is None:
            order_by = DEFAULT_ORDER_BY
        # Apply ordering and pagination
        if order_by.direction == OrderDirection.ASC:
            base_query = base_query.order_by(
                sqlalchemy.asc(getattr(functions_table.c, order_by.field)),
                functions_table.c.uuid,
            )
        else:
            base_query = base_query.order_by(
                sqlalchemy.desc(getattr(functions_table.c, order_by.field)),
                functions_table.c.uuid,
            )

        function_rows = [
            RegisteredFunctionDB.model_validate(row)
            async for row in await conn.stream(base_query.offset(pagination_offset).limit(pagination_limit))
        ]

        return function_rows, PageMetaInfoLimitOffset(
            total=total_count,
            offset=pagination_offset,
            limit=pagination_limit,
            count=len(function_rows),
        )


async def delete_function(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    user_id: UserID,
    product_name: ProductName,
    function_id: FunctionID,
    force: bool = False,
) -> None:
    async with transaction_context(get_asyncpg_engine(app), connection) as transaction:
        await check_user_permissions(
            app,
            connection=transaction,
            user_id=user_id,
            product_name=product_name,
            object_id=function_id,
            object_type="function",
            permissions=["write"],
        )

        # Check if the function exists
        result = await transaction.execute(functions_table.select().where(functions_table.c.uuid == function_id))
        row = result.one_or_none()

        if row is None:
            raise FunctionIDNotFoundError(function_id=function_id)

        # Check for existing function jobs if force is not True
        if not force:
            jobs_result = await transaction.execute(
                function_jobs_table.select()
                .with_only_columns(func.count())
                .where(function_jobs_table.c.function_uuid == function_id)
            )
            jobs_count = jobs_result.scalar() or 0

            if jobs_count > 0:
                raise FunctionHasJobsCannotDeleteError(function_id=function_id, jobs_count=jobs_count)

        # Proceed with deletion
        await transaction.execute(functions_table.delete().where(functions_table.c.uuid == function_id))


async def update_function(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    user_id: UserID,
    product_name: ProductName,
    function_id: FunctionID,
    function: FunctionUpdate,
) -> RegisteredFunctionDB:
    async with transaction_context(get_asyncpg_engine(app), connection) as transaction:
        await check_user_permissions(
            app,
            transaction,
            user_id=user_id,
            product_name=product_name,
            object_id=function_id,
            object_type="function",
            permissions=["read", "write"],
        )

        result = await transaction.execute(
            functions_table.update()
            .where(functions_table.c.uuid == function_id)
            .values(**function.model_dump(exclude_none=True, exclude_unset=True))
            .returning(*_FUNCTIONS_TABLE_COLS)
        )
        row = result.one_or_none()

        if row is None:
            raise FunctionIDNotFoundError(function_id=function_id)

        return RegisteredFunctionDB.model_validate(row)
