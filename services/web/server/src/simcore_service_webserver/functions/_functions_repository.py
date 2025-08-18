# pylint: disable=too-many-arguments

import json
from typing import Final, Literal
from uuid import UUID

import sqlalchemy
from aiohttp import web
from models_library.basic_types import IDStr
from models_library.functions import (
    FunctionAccessRightsDB,
    FunctionClass,
    FunctionID,
    FunctionInputs,
    FunctionInputSchema,
    FunctionJobAccessRightsDB,
    FunctionJobClassSpecificData,
    FunctionJobCollectionAccessRightsDB,
    FunctionJobCollectionID,
    FunctionJobCollectionsListFilters,
    FunctionJobID,
    FunctionJobStatus,
    FunctionOutputs,
    FunctionOutputSchema,
    FunctionsApiAccessRights,
    FunctionUpdate,
    FunctionUserApiAccessRights,
    RegisteredFunctionDB,
    RegisteredFunctionJobCollectionDB,
    RegisteredFunctionJobDB,
)
from models_library.functions_errors import (
    FunctionBaseError,
    FunctionExecuteAccessDeniedError,
    FunctionIDNotFoundError,
    FunctionJobCollectionExecuteAccessDeniedError,
    FunctionJobCollectionIDNotFoundError,
    FunctionJobCollectionReadAccessDeniedError,
    FunctionJobCollectionsExecuteApiAccessDeniedError,
    FunctionJobCollectionsReadApiAccessDeniedError,
    FunctionJobCollectionsWriteApiAccessDeniedError,
    FunctionJobCollectionWriteAccessDeniedError,
    FunctionJobExecuteAccessDeniedError,
    FunctionJobIDNotFoundError,
    FunctionJobReadAccessDeniedError,
    FunctionJobsExecuteApiAccessDeniedError,
    FunctionJobsReadApiAccessDeniedError,
    FunctionJobsWriteApiAccessDeniedError,
    FunctionJobWriteAccessDeniedError,
    FunctionReadAccessDeniedError,
    FunctionsExecuteApiAccessDeniedError,
    FunctionsReadApiAccessDeniedError,
    FunctionsWriteApiAccessDeniedError,
    FunctionWriteAccessDeniedError,
)
from models_library.groups import GroupID
from models_library.products import ProductName
from models_library.rest_ordering import OrderBy, OrderDirection
from models_library.rest_pagination import PageMetaInfoLimitOffset
from models_library.users import UserID
from pydantic import TypeAdapter
from simcore_postgres_database.models.funcapi_api_access_rights_table import (
    funcapi_api_access_rights_table,
)
from simcore_postgres_database.models.funcapi_function_job_collections_access_rights_table import (
    function_job_collections_access_rights_table,
)
from simcore_postgres_database.models.funcapi_function_job_collections_table import (
    function_job_collections_table,
)
from simcore_postgres_database.models.funcapi_function_job_collections_to_function_jobs_table import (
    function_job_collections_to_function_jobs_table,
)
from simcore_postgres_database.models.funcapi_function_jobs_access_rights_table import (
    function_jobs_access_rights_table,
)
from simcore_postgres_database.models.funcapi_function_jobs_table import (
    function_jobs_table,
)
from simcore_postgres_database.models.funcapi_functions_access_rights_table import (
    functions_access_rights_table,
)
from simcore_postgres_database.models.funcapi_functions_table import functions_table
from simcore_postgres_database.utils_repos import (
    get_columns_from_db_model,
    pass_or_acquire_connection,
    transaction_context,
)
from sqlalchemy import String, Text, cast
from sqlalchemy.engine.row import Row
from sqlalchemy.ext.asyncio import AsyncConnection
from sqlalchemy.sql import ColumnElement, func

from ..db.plugin import get_asyncpg_engine
from ..groups.api import list_all_user_groups_ids
from ..users import users_service

_FUNCTIONS_TABLE_COLS = get_columns_from_db_model(functions_table, RegisteredFunctionDB)
_FUNCTION_JOBS_TABLE_COLS = get_columns_from_db_model(
    function_jobs_table, RegisteredFunctionJobDB
)
_FUNCTION_JOB_COLLECTIONS_TABLE_COLS = get_columns_from_db_model(
    function_job_collections_table, RegisteredFunctionJobCollectionDB
)
_FUNCTIONS_ACCESS_RIGHTS_TABLE_COLS = get_columns_from_db_model(
    functions_access_rights_table, FunctionAccessRightsDB
)
_FUNCTION_JOBS_ACCESS_RIGHTS_TABLE_COLS = get_columns_from_db_model(
    function_jobs_access_rights_table, FunctionJobAccessRightsDB
)
_FUNCTION_JOB_COLLECTIONS_ACCESS_RIGHTS_TABLE_COLS = get_columns_from_db_model(
    function_job_collections_access_rights_table, FunctionJobCollectionAccessRightsDB
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

        user_primary_group_id = await users_service.get_user_primary_group_id(
            app, user_id=user_id
        )
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


async def create_function_job(  # noqa: PLR0913
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    user_id: UserID,
    product_name: ProductName,
    function_class: FunctionClass,
    function_uid: FunctionID,
    title: str,
    description: str,
    inputs: FunctionInputs,
    outputs: FunctionOutputs,
    class_specific_data: FunctionJobClassSpecificData,
) -> RegisteredFunctionJobDB:
    async with transaction_context(get_asyncpg_engine(app), connection) as transaction:
        await check_user_api_access_rights(
            app,
            connection=transaction,
            user_id=user_id,
            product_name=product_name,
            api_access_rights=[
                FunctionsApiAccessRights.WRITE_FUNCTION_JOBS,
            ],
        )
        result = await transaction.execute(
            function_jobs_table.insert()
            .values(
                function_uuid=function_uid,
                inputs=inputs,
                outputs=outputs,
                function_class=function_class,
                class_specific_data=class_specific_data,
                title=title,
                description=description,
                status="created",
            )
            .returning(*_FUNCTION_JOBS_TABLE_COLS)
        )
        row = result.one()

        registered_function_job = RegisteredFunctionJobDB.model_validate(row)

        user_primary_group_id = await users_service.get_user_primary_group_id(
            app, user_id=user_id
        )
        await _internal_set_group_permissions(
            app,
            connection=transaction,
            permission_group_id=user_primary_group_id,
            product_name=product_name,
            object_type="function_job",
            object_ids=[registered_function_job.uuid],
            read=True,
            write=True,
            execute=True,
        )

    return registered_function_job


async def create_function_job_collection(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    user_id: UserID,
    product_name: ProductName,
    title: str,
    description: str,
    job_ids: list[FunctionJobID],
) -> tuple[RegisteredFunctionJobCollectionDB, list[FunctionJobID]]:
    async with transaction_context(get_asyncpg_engine(app), connection) as transaction:
        await check_user_api_access_rights(
            app,
            connection=transaction,
            user_id=user_id,
            product_name=product_name,
            api_access_rights=[
                FunctionsApiAccessRights.WRITE_FUNCTION_JOB_COLLECTIONS,
            ],
        )
        for job_id in job_ids:
            await check_user_permissions(
                app,
                connection=transaction,
                user_id=user_id,
                product_name=product_name,
                object_type="function_job",
                object_id=job_id,
                permissions=["read"],
            )

        result = await transaction.execute(
            function_job_collections_table.insert()
            .values(
                title=title,
                description=description,
            )
            .returning(*_FUNCTION_JOB_COLLECTIONS_TABLE_COLS)
        )
        row = result.one_or_none()

        assert row is not None, (
            "No row was returned from the database after creating function job collection."
            f" Function job collection: {title}"
        )  # nosec

        function_job_collection_db = RegisteredFunctionJobCollectionDB.model_validate(
            row
        )
        job_collection_entries: list[Row] = []
        for job_id in job_ids:
            result = await transaction.execute(
                function_job_collections_to_function_jobs_table.insert()
                .values(
                    function_job_collection_uuid=function_job_collection_db.uuid,
                    function_job_uuid=job_id,
                )
                .returning(
                    function_job_collections_to_function_jobs_table.c.function_job_collection_uuid,
                    function_job_collections_to_function_jobs_table.c.function_job_uuid,
                )
            )
            entry = result.one_or_none()
            assert entry is not None, (
                f"No row was returned from the database after creating function job collection entry {title}."
                f" Job ID: {job_id}"
            )  # nosec
            job_collection_entries.append(entry)

        user_primary_group_id = await users_service.get_user_primary_group_id(
            app, user_id=user_id
        )
        await _internal_set_group_permissions(
            app,
            connection=transaction,
            permission_group_id=user_primary_group_id,
            product_name=product_name,
            object_type="function_job_collection",
            object_ids=[function_job_collection_db.uuid],
            read=True,
            write=True,
            execute=True,
        )

    return function_job_collection_db, [
        entry.function_job_uuid for entry in job_collection_entries
    ]


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

        result = await conn.execute(
            functions_table.select().where(functions_table.c.uuid == function_id)
        )
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
        attributes_filters.append(
            functions_table.c.function_class == filter_by_function_class.value
        )

    if search_by_multi_columns is not None:
        attributes_filters.append(
            (functions_table.c.title.ilike(f"%{search_by_multi_columns}%"))
            | (functions_table.c.description.ilike(f"%{search_by_multi_columns}%"))
            | (
                cast(functions_table.c.uuid, String).ilike(
                    f"%{search_by_multi_columns}%"
                )
            )
        )

    if search_by_function_title is not None:
        attributes_filters.append(
            functions_table.c.title.ilike(f"%{search_by_function_title}%")
        )

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

        # Build the base query with join to access rights table
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
        )

        # Get total count
        total_count = await conn.scalar(
            func.count().select().select_from(base_query.subquery())
        )
        if total_count == 0:
            return [], PageMetaInfoLimitOffset(
                total=0, offset=pagination_offset, limit=pagination_limit, count=0
            )

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
            async for row in await conn.stream(
                base_query.offset(pagination_offset).limit(pagination_limit)
            )
        ]

        return function_rows, PageMetaInfoLimitOffset(
            total=total_count,
            offset=pagination_offset,
            limit=pagination_limit,
            count=len(function_rows),
        )


async def list_function_jobs(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    user_id: UserID,
    product_name: ProductName,
    pagination_limit: int,
    pagination_offset: int,
    filter_by_function_id: FunctionID | None = None,
    filter_by_function_job_ids: list[FunctionJobID] | None = None,
    filter_by_function_job_collection_id: FunctionJobCollectionID | None = None,
) -> tuple[list[RegisteredFunctionJobDB], PageMetaInfoLimitOffset]:
    async with pass_or_acquire_connection(get_asyncpg_engine(app), connection) as conn:
        await check_user_api_access_rights(
            app,
            connection=conn,
            user_id=user_id,
            product_name=product_name,
            api_access_rights=[FunctionsApiAccessRights.READ_FUNCTION_JOBS],
        )
        user_groups = await list_all_user_groups_ids(app, user_id=user_id)

        access_subquery = (
            function_jobs_access_rights_table.select()
            .with_only_columns(function_jobs_access_rights_table.c.function_job_uuid)
            .where(
                function_jobs_access_rights_table.c.group_id.in_(user_groups),
                function_jobs_access_rights_table.c.product_name == product_name,
                function_jobs_access_rights_table.c.read,
            )
        )

        filter_conditions = sqlalchemy.and_(
            function_jobs_table.c.uuid.in_(access_subquery),
            (
                function_jobs_table.c.function_uuid == filter_by_function_id
                if filter_by_function_id
                else sqlalchemy.sql.true()
            ),
            (
                function_jobs_table.c.uuid.in_(filter_by_function_job_ids)
                if filter_by_function_job_ids
                else sqlalchemy.sql.true()
            ),
        )

        if filter_by_function_job_collection_id:
            collection_subquery = (
                function_job_collections_to_function_jobs_table.select()
                .with_only_columns(
                    function_job_collections_to_function_jobs_table.c.function_job_uuid
                )
                .where(
                    function_job_collections_to_function_jobs_table.c.function_job_collection_uuid
                    == filter_by_function_job_collection_id
                )
            )
            filter_conditions = sqlalchemy.and_(
                filter_conditions,
                function_jobs_table.c.uuid.in_(collection_subquery),
            )

        total_count_result = await conn.scalar(
            func.count()
            .select()
            .select_from(function_jobs_table)
            .where(filter_conditions)
        )
        if total_count_result == 0:
            return [], PageMetaInfoLimitOffset(
                total=0, offset=pagination_offset, limit=pagination_limit, count=0
            )
        results = [
            RegisteredFunctionJobDB.model_validate(row)
            async for row in await conn.stream(
                function_jobs_table.select()
                .where(filter_conditions)
                .offset(pagination_offset)
                .limit(pagination_limit)
            )
        ]

        return results, PageMetaInfoLimitOffset(
            total=total_count_result,
            offset=pagination_offset,
            limit=pagination_limit,
            count=len(results),
        )


async def get_function_job_status(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    user_id: UserID,
    product_name: ProductName,
    function_job_id: FunctionJobID,
) -> FunctionJobStatus:
    async with pass_or_acquire_connection(get_asyncpg_engine(app), connection) as conn:
        await check_user_permissions(
            app,
            connection=conn,
            user_id=user_id,
            product_name=product_name,
            object_type="function_job",
            object_id=function_job_id,
            permissions=["read"],
        )

        result = await conn.execute(
            function_jobs_table.select().where(
                function_jobs_table.c.uuid == function_job_id
            )
        )
        row = result.one_or_none()

        if row is None:
            raise FunctionJobIDNotFoundError(function_job_id=function_job_id)

        return FunctionJobStatus(status=row.status)


async def get_function_job_outputs(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    user_id: UserID,
    product_name: ProductName,
    function_job_id: FunctionJobID,
) -> FunctionOutputs:
    async with pass_or_acquire_connection(get_asyncpg_engine(app), connection) as conn:
        await check_user_permissions(
            app,
            connection=conn,
            user_id=user_id,
            product_name=product_name,
            object_type="function_job",
            object_id=function_job_id,
            permissions=["read"],
        )

        result = await conn.execute(
            function_jobs_table.select().where(
                function_jobs_table.c.uuid == function_job_id
            )
        )
        row = result.one_or_none()

        if row is None:
            raise FunctionJobIDNotFoundError(function_job_id=function_job_id)

        return TypeAdapter(FunctionOutputs).validate_python(row.outputs)


async def update_function_job_status(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    user_id: UserID,
    product_name: ProductName,
    function_job_id: FunctionJobID,
    job_status: FunctionJobStatus,
) -> FunctionJobStatus:
    async with transaction_context(get_asyncpg_engine(app), connection) as transaction:
        await check_user_permissions(
            app,
            connection=transaction,
            user_id=user_id,
            product_name=product_name,
            object_type="function_job",
            object_id=function_job_id,
            permissions=["write"],
        )

        result = await transaction.execute(
            function_jobs_table.update()
            .where(function_jobs_table.c.uuid == function_job_id)
            .values(status=job_status.status)
            .returning(function_jobs_table.c.status)
        )
        row = result.one_or_none()

        if row is None:
            raise FunctionJobIDNotFoundError(function_job_id=function_job_id)

        return FunctionJobStatus(status=row.status)


async def update_function_job_outputs(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    user_id: UserID,
    product_name: ProductName,
    function_job_id: FunctionJobID,
    outputs: FunctionOutputs,
) -> FunctionOutputs:
    async with transaction_context(get_asyncpg_engine(app), connection) as transaction:
        await check_user_permissions(
            app,
            connection=transaction,
            user_id=user_id,
            product_name=product_name,
            object_type="function_job",
            object_id=function_job_id,
            permissions=["write"],
        )

        result = await transaction.execute(
            function_jobs_table.update()
            .where(function_jobs_table.c.uuid == function_job_id)
            .values(outputs=outputs)
            .returning(function_jobs_table.c.outputs)
        )
        row = result.one_or_none()

        if row is None:
            raise FunctionJobIDNotFoundError(function_job_id=function_job_id)

        return TypeAdapter(FunctionOutputs).validate_python(row.outputs)


async def list_function_job_collections(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    user_id: UserID,
    product_name: ProductName,
    pagination_limit: int,
    pagination_offset: int,
    filters: FunctionJobCollectionsListFilters | None = None,
) -> tuple[
    list[tuple[RegisteredFunctionJobCollectionDB, list[FunctionJobID]]],
    PageMetaInfoLimitOffset,
]:
    """
    Returns a list of function job collections and their associated job ids.
    Filters the collections to include only those that have function jobs with the specified function id if filters.has_function_id is provided.
    """
    async with pass_or_acquire_connection(get_asyncpg_engine(app), connection) as conn:
        await check_user_api_access_rights(
            app,
            connection=conn,
            user_id=user_id,
            product_name=product_name,
            api_access_rights=[
                FunctionsApiAccessRights.READ_FUNCTION_JOB_COLLECTIONS,
            ],
        )

        filter_condition: sqlalchemy.sql.ColumnElement = sqlalchemy.sql.true()

        if filters and filters.has_function_id:
            function_id = TypeAdapter(FunctionID).validate_python(
                filters.has_function_id
            )
            subquery = (
                function_job_collections_to_function_jobs_table.select()
                .with_only_columns(
                    func.distinct(
                        function_job_collections_to_function_jobs_table.c.function_job_collection_uuid
                    )
                )
                .join(
                    function_jobs_table,
                    function_job_collections_to_function_jobs_table.c.function_job_uuid
                    == function_jobs_table.c.uuid,
                )
                .where(function_jobs_table.c.function_uuid == function_id)
            )
            filter_condition = function_job_collections_table.c.uuid.in_(subquery)
        user_groups = await list_all_user_groups_ids(app, user_id=user_id)

        access_subquery = (
            function_job_collections_access_rights_table.select()
            .with_only_columns(
                function_job_collections_access_rights_table.c.function_job_collection_uuid
            )
            .where(
                function_job_collections_access_rights_table.c.group_id.in_(
                    user_groups
                ),
                function_job_collections_access_rights_table.c.product_name
                == product_name,
                function_job_collections_access_rights_table.c.read,
            )
        )

        filter_and_access_condition = sqlalchemy.and_(
            filter_condition,
            function_job_collections_table.c.uuid.in_(access_subquery),
        )

        total_count_result = await conn.scalar(
            func.count()
            .select()
            .select_from(function_job_collections_table)
            .where(filter_and_access_condition)
        )
        if total_count_result == 0:
            return [], PageMetaInfoLimitOffset(
                total=0, offset=pagination_offset, limit=pagination_limit, count=0
            )

        query = function_job_collections_table.select().where(
            filter_and_access_condition
        )

        collections = []
        async for row in await conn.stream(
            query.offset(pagination_offset).limit(pagination_limit)
        ):
            collection = RegisteredFunctionJobCollectionDB.model_validate(row)
            job_ids = [
                job_row.function_job_uuid
                async for job_row in await conn.stream(
                    function_job_collections_to_function_jobs_table.select().where(
                        function_job_collections_to_function_jobs_table.c.function_job_collection_uuid
                        == row.uuid
                    )
                )
            ]
            collections.append((collection, job_ids))
        return collections, PageMetaInfoLimitOffset(
            total=total_count_result,
            offset=pagination_offset,
            limit=pagination_limit,
            count=len(collections),
        )


async def delete_function(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    user_id: UserID,
    product_name: ProductName,
    function_id: FunctionID,
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
        result = await transaction.execute(
            functions_table.select().where(functions_table.c.uuid == function_id)
        )
        row = result.one_or_none()

        if row is None:
            raise FunctionIDNotFoundError(function_id=function_id)

        # Proceed with deletion
        await transaction.execute(
            functions_table.delete().where(functions_table.c.uuid == function_id)
        )


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


async def get_function_job(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    user_id: UserID,
    product_name: ProductName,
    function_job_id: FunctionID,
) -> RegisteredFunctionJobDB:
    async with pass_or_acquire_connection(get_asyncpg_engine(app), connection) as conn:
        await check_user_permissions(
            app,
            connection=conn,
            user_id=user_id,
            product_name=product_name,
            object_id=function_job_id,
            object_type="function_job",
            permissions=["read"],
        )

        result = await conn.execute(
            function_jobs_table.select().where(
                function_jobs_table.c.uuid == function_job_id
            )
        )
        row = result.one_or_none()

        if row is None:
            raise FunctionJobIDNotFoundError(function_job_id=function_job_id)

        return RegisteredFunctionJobDB.model_validate(row)


async def delete_function_job(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    user_id: UserID,
    product_name: ProductName,
    function_job_id: FunctionID,
) -> None:
    async with transaction_context(get_asyncpg_engine(app), connection) as transaction:
        await check_user_permissions(
            app,
            connection=transaction,
            user_id=user_id,
            product_name=product_name,
            object_id=function_job_id,
            object_type="function_job",
            permissions=["write"],
        )

        # Check if the function job exists
        result = await transaction.execute(
            function_jobs_table.select().where(
                function_jobs_table.c.uuid == function_job_id
            )
        )
        row = result.one_or_none()
        if row is None:
            raise FunctionJobIDNotFoundError(function_job_id=function_job_id)

        # Proceed with deletion
        await transaction.execute(
            function_jobs_table.delete().where(
                function_jobs_table.c.uuid == function_job_id
            )
        )


async def find_cached_function_jobs(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    user_id: UserID,
    function_id: FunctionID,
    product_name: ProductName,
    inputs: FunctionInputs,
) -> list[RegisteredFunctionJobDB] | None:
    async with pass_or_acquire_connection(get_asyncpg_engine(app), connection) as conn:
        jobs: list[RegisteredFunctionJobDB] = []
        async for row in await conn.stream(
            function_jobs_table.select().where(
                function_jobs_table.c.function_uuid == function_id,
                cast(function_jobs_table.c.inputs, Text) == json.dumps(inputs),
            )
        ):
            job = RegisteredFunctionJobDB.model_validate(row)
            try:
                await check_user_permissions(
                    app,
                    connection=conn,
                    user_id=user_id,
                    product_name=product_name,
                    object_id=job.uuid,
                    object_type="function_job",
                    permissions=["read"],
                )
            except FunctionJobReadAccessDeniedError:
                continue

            jobs.append(job)

        if len(jobs) > 0:
            return jobs

        return None


async def get_function_job_collection(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    user_id: UserID,
    product_name: ProductName,
    function_job_collection_id: FunctionID,
) -> tuple[RegisteredFunctionJobCollectionDB, list[FunctionJobID]]:
    async with pass_or_acquire_connection(get_asyncpg_engine(app), connection) as conn:
        await check_user_permissions(
            app,
            connection=conn,
            user_id=user_id,
            product_name=product_name,
            object_id=function_job_collection_id,
            object_type="function_job_collection",
            permissions=["read"],
        )

        result = await conn.execute(
            function_job_collections_table.select().where(
                function_job_collections_table.c.uuid == function_job_collection_id
            )
        )
        row = result.one_or_none()

        if row is None:
            raise FunctionJobCollectionIDNotFoundError(
                function_job_collection_id=function_job_collection_id
            )

        # Retrieve associated job ids from the join table
        job_ids = [
            job_row.function_job_uuid
            async for job_row in await conn.stream(
                function_job_collections_to_function_jobs_table.select().where(
                    function_job_collections_to_function_jobs_table.c.function_job_collection_uuid
                    == row.uuid
                )
            )
        ]

        job_collection = RegisteredFunctionJobCollectionDB.model_validate(row)

    return job_collection, job_ids


async def delete_function_job_collection(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    user_id: UserID,
    product_name: ProductName,
    function_job_collection_id: FunctionID,
) -> None:
    async with transaction_context(get_asyncpg_engine(app), connection) as transaction:
        await check_user_permissions(
            app,
            connection=transaction,
            user_id=user_id,
            product_name=product_name,
            object_id=function_job_collection_id,
            object_type="function_job_collection",
            permissions=["write"],
        )

        # Check if the function job collection exists
        result = await transaction.execute(
            function_job_collections_table.select().where(
                function_job_collections_table.c.uuid == function_job_collection_id
            )
        )
        row = result.one_or_none()
        if row is None:
            raise FunctionJobCollectionIDNotFoundError(
                function_job_collection_id=function_job_collection_id
            )
        # Proceed with deletion
        await transaction.execute(
            function_job_collections_table.delete().where(
                function_job_collections_table.c.uuid == function_job_collection_id
            )
        )
        await transaction.execute(
            function_job_collections_to_function_jobs_table.delete().where(
                function_job_collections_to_function_jobs_table.c.function_job_collection_uuid
                == function_job_collection_id
            )
        )


async def set_group_permissions(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    user_id: UserID,
    permission_group_id: GroupID,
    product_name: ProductName,
    object_type: Literal["function", "function_job", "function_job_collection"],
    object_ids: list[UUID],
    read: bool | None = None,
    write: bool | None = None,
    execute: bool | None = None,
) -> None:
    async with pass_or_acquire_connection(get_asyncpg_engine(app), connection) as conn:
        for object_id in object_ids:
            await check_user_permissions(
                app,
                connection=conn,
                user_id=user_id,
                product_name=product_name,
                object_id=object_id,
                object_type=object_type,
                permissions=["write"],
            )

        await _internal_set_group_permissions(
            app,
            connection=connection,
            permission_group_id=permission_group_id,
            product_name=product_name,
            object_type=object_type,
            object_ids=object_ids,
            read=read,
            write=write,
            execute=execute,
        )


async def remove_group_permissions(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    user_id: UserID,
    permission_group_id: GroupID,
    product_name: ProductName,
    object_type: Literal["function", "function_job", "function_job_collection"],
    object_ids: list[UUID],
) -> None:
    async with pass_or_acquire_connection(get_asyncpg_engine(app), connection) as conn:
        for object_id in object_ids:
            await check_user_permissions(
                app,
                connection=conn,
                user_id=user_id,
                product_name=product_name,
                object_id=object_id,
                object_type=object_type,
                permissions=["write"],
            )

        await _internal_remove_group_permissions(
            app,
            connection=connection,
            permission_group_id=permission_group_id,
            product_name=product_name,
            object_type=object_type,
            object_ids=object_ids,
        )


async def _internal_remove_group_permissions(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    permission_group_id: GroupID,
    product_name: ProductName,
    object_type: Literal["function", "function_job", "function_job_collection"],
    object_ids: list[UUID],
) -> None:
    access_rights_table = None
    field_name = None

    if object_type == "function":
        access_rights_table = functions_access_rights_table
        field_name = "function_uuid"
    elif object_type == "function_job":
        access_rights_table = function_jobs_access_rights_table
        field_name = "function_job_uuid"
    elif object_type == "function_job_collection":
        access_rights_table = function_job_collections_access_rights_table
        field_name = "function_job_collection_uuid"

    assert access_rights_table is not None  # nosec
    assert field_name is not None  # nosec

    async with transaction_context(get_asyncpg_engine(app), connection) as transaction:
        for object_id in object_ids:
            await transaction.execute(
                access_rights_table.delete().where(
                    getattr(access_rights_table.c, field_name) == object_id,
                    access_rights_table.c.group_id == permission_group_id,
                    access_rights_table.c.product_name == product_name,
                )
            )


async def _internal_set_group_permissions(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    permission_group_id: GroupID,
    product_name: ProductName,
    object_type: Literal["function", "function_job", "function_job_collection"],
    object_ids: list[UUID],
    read: bool | None = None,
    write: bool | None = None,
    execute: bool | None = None,
) -> None:
    access_rights_table = None
    field_name = None
    if object_type == "function":
        access_rights_table = functions_access_rights_table
        field_name = "function_uuid"
    elif object_type == "function_job":
        access_rights_table = function_jobs_access_rights_table
        field_name = "function_job_uuid"
    elif object_type == "function_job_collection":
        access_rights_table = function_job_collections_access_rights_table
        field_name = "function_job_collection_uuid"

    assert access_rights_table is not None  # nosec
    assert field_name is not None  # nosec

    async with transaction_context(get_asyncpg_engine(app), connection) as transaction:
        for object_id in object_ids:
            # Check if the group already has access rights for the function
            result = await transaction.execute(
                access_rights_table.select().where(
                    getattr(access_rights_table.c, field_name) == object_id,
                    access_rights_table.c.group_id == permission_group_id,
                )
            )
            row = result.one_or_none()

            if row is None:
                # Insert new access rights if the group does not have any
                await transaction.execute(
                    access_rights_table.insert().values(
                        **{field_name: object_id},
                        group_id=permission_group_id,
                        product_name=product_name,
                        read=read if read is not None else False,
                        write=write if write is not None else False,
                        execute=execute if execute is not None else False,
                    )
                )
            else:
                # Update existing access rights only for non-None values
                update_values = {
                    "read": read if read is not None else row["read"],
                    "write": write if write is not None else row["write"],
                    "execute": execute if execute is not None else row["execute"],
                }

                await transaction.execute(
                    access_rights_table.update()
                    .where(
                        getattr(access_rights_table.c, field_name) == object_id,
                        access_rights_table.c.group_id == permission_group_id,
                    )
                    .values(**update_values)
                )


async def get_user_api_access_rights(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    user_id: UserID,
    product_name: ProductName,
) -> FunctionUserApiAccessRights:
    async with pass_or_acquire_connection(get_asyncpg_engine(app), connection) as conn:
        user_groups = await list_all_user_groups_ids(app, user_id=user_id)

        # Initialize combined permissions with False values
        combined_permissions = FunctionUserApiAccessRights(
            user_id=user_id,
            read_functions=False,
            write_functions=False,
            execute_functions=False,
            read_function_jobs=False,
            write_function_jobs=False,
            execute_function_jobs=False,
            read_function_job_collections=False,
            write_function_job_collections=False,
            execute_function_job_collections=False,
        )

        # Process each row only once and combine permissions
        async for row in await conn.stream(
            funcapi_api_access_rights_table.select().where(
                funcapi_api_access_rights_table.c.group_id.in_(user_groups),
                funcapi_api_access_rights_table.c.product_name == product_name,
            )
        ):
            combined_permissions.read_functions |= row.read_functions
            combined_permissions.write_functions |= row.write_functions
            combined_permissions.execute_functions |= row.execute_functions
            combined_permissions.read_function_jobs |= row.read_function_jobs
            combined_permissions.write_function_jobs |= row.write_function_jobs
            combined_permissions.execute_function_jobs |= row.execute_function_jobs
            combined_permissions.read_function_job_collections |= (
                row.read_function_job_collections
            )
            combined_permissions.write_function_job_collections |= (
                row.write_function_job_collections
            )
            combined_permissions.execute_function_job_collections |= (
                row.execute_function_job_collections
            )

        return combined_permissions


async def get_user_permissions(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    user_id: UserID,
    product_name: ProductName,
    object_id: UUID,
    object_type: Literal["function", "function_job", "function_job_collection"],
) -> FunctionAccessRightsDB | None:
    async with pass_or_acquire_connection(get_asyncpg_engine(app), connection) as conn:
        await check_exists(
            app,
            conn,
            object_id=object_id,
            object_type=object_type,
        )

        access_rights_table = None
        cols = None
        if object_type == "function":
            access_rights_table = functions_access_rights_table
            cols = _FUNCTIONS_ACCESS_RIGHTS_TABLE_COLS
        elif object_type == "function_job":
            access_rights_table = function_jobs_access_rights_table
            cols = _FUNCTION_JOBS_ACCESS_RIGHTS_TABLE_COLS
        elif object_type == "function_job_collection":
            access_rights_table = function_job_collections_access_rights_table
            cols = _FUNCTION_JOB_COLLECTIONS_ACCESS_RIGHTS_TABLE_COLS
        assert access_rights_table is not None  # nosec

        user_groups = await list_all_user_groups_ids(app, user_id=user_id)

        # Initialize combined permissions with False values
        combined_permissions = FunctionAccessRightsDB(
            read=False, write=False, execute=False
        )

        # Process each row only once and combine permissions
        async for row in await conn.stream(
            access_rights_table.select()
            .with_only_columns(*cols)
            .where(
                getattr(access_rights_table.c, f"{object_type}_uuid") == object_id,
                access_rights_table.c.product_name == product_name,
                access_rights_table.c.group_id.in_(user_groups),
            )
        ):
            combined_permissions.read |= row.read
            combined_permissions.write |= row.write
            combined_permissions.execute |= row.execute

        return combined_permissions


async def check_exists(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    object_id: UUID,
    object_type: Literal["function", "function_job", "function_job_collection"],
) -> bool:
    """
    Checks if the object exists in the database.
    """
    error: (
        FunctionIDNotFoundError
        | FunctionJobIDNotFoundError
        | FunctionJobCollectionIDNotFoundError
    )  # This is to avoid mypy bug
    match object_type:
        case "function":
            main_table = functions_table
            error = FunctionIDNotFoundError(function_id=object_id)
        case "function_job":
            main_table = function_jobs_table
            error = FunctionJobIDNotFoundError(function_job_id=object_id)
        case "function_job_collection":
            main_table = function_job_collections_table
            error = FunctionJobCollectionIDNotFoundError(
                function_job_collection_id=object_id
            )

    async with pass_or_acquire_connection(get_asyncpg_engine(app), connection) as conn:
        result = await conn.execute(
            main_table.select().where(main_table.c.uuid == object_id)
        )
        row = result.one_or_none()

        if row is None:
            raise error
        return True


async def check_user_permissions(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    user_id: UserID,
    product_name: ProductName,
    object_id: UUID,
    object_type: Literal["function", "function_job", "function_job_collection"],
    permissions: list[Literal["read", "write", "execute"]],
) -> bool:

    api_access_rights = [
        getattr(
            FunctionsApiAccessRights, f"{permission.upper()}_{object_type.upper()}S"
        )
        for permission in permissions
    ]
    await check_user_api_access_rights(
        app,
        connection=connection,
        user_id=user_id,
        product_name=product_name,
        api_access_rights=api_access_rights,
    )

    user_permissions = await get_user_permissions(
        app,
        connection=connection,
        user_id=user_id,
        product_name=product_name,
        object_id=object_id,
        object_type=object_type,
    )

    errors = None
    match object_type:
        case "function":
            errors = {
                "read": FunctionReadAccessDeniedError(
                    user_id=user_id, function_id=object_id
                ),
                "write": FunctionWriteAccessDeniedError(
                    user_id=user_id, function_id=object_id
                ),
                "execute": FunctionExecuteAccessDeniedError(
                    user_id=user_id, function_id=object_id
                ),
            }
        case "function_job":
            errors = {
                "read": FunctionJobReadAccessDeniedError(
                    user_id=user_id, function_job_id=object_id
                ),
                "write": FunctionJobWriteAccessDeniedError(
                    user_id=user_id, function_job_id=object_id
                ),
                "execute": FunctionJobExecuteAccessDeniedError(
                    user_id=user_id, function_job_id=object_id
                ),
            }
        case "function_job_collection":
            errors = {
                "read": FunctionJobCollectionReadAccessDeniedError(
                    user_id=user_id, function_job_collection_id=object_id
                ),
                "write": FunctionJobCollectionWriteAccessDeniedError(
                    user_id=user_id, function_job_collection_id=object_id
                ),
                "execute": FunctionJobCollectionExecuteAccessDeniedError(
                    user_id=user_id, function_job_collection_id=object_id
                ),
            }
    assert errors is not None

    if user_permissions is None:
        raise errors["read"]

    for permission in permissions:
        if not getattr(user_permissions, permission):
            raise errors[permission]

    return True


_ERRORS_MAP: Final[dict[FunctionsApiAccessRights, type[FunctionBaseError]]] = {
    FunctionsApiAccessRights.READ_FUNCTIONS: FunctionsReadApiAccessDeniedError,
    FunctionsApiAccessRights.WRITE_FUNCTIONS: FunctionsWriteApiAccessDeniedError,
    FunctionsApiAccessRights.EXECUTE_FUNCTIONS: FunctionsExecuteApiAccessDeniedError,
    FunctionsApiAccessRights.READ_FUNCTION_JOBS: FunctionJobsReadApiAccessDeniedError,
    FunctionsApiAccessRights.WRITE_FUNCTION_JOBS: FunctionJobsWriteApiAccessDeniedError,
    FunctionsApiAccessRights.EXECUTE_FUNCTION_JOBS: FunctionJobsExecuteApiAccessDeniedError,
    FunctionsApiAccessRights.READ_FUNCTION_JOB_COLLECTIONS: FunctionJobCollectionsReadApiAccessDeniedError,
    FunctionsApiAccessRights.WRITE_FUNCTION_JOB_COLLECTIONS: FunctionJobCollectionsWriteApiAccessDeniedError,
    FunctionsApiAccessRights.EXECUTE_FUNCTION_JOB_COLLECTIONS: FunctionJobCollectionsExecuteApiAccessDeniedError,
}


async def check_user_api_access_rights(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    user_id: UserID,
    product_name: ProductName,
    api_access_rights: list[FunctionsApiAccessRights],
) -> bool:
    user_api_access_rights = await get_user_api_access_rights(
        app, connection=connection, user_id=user_id, product_name=product_name
    )

    for api_access_right in api_access_rights:
        if not getattr(user_api_access_rights, api_access_right):
            raise _ERRORS_MAP[api_access_right](user_id=user_id)

    return True
