# pylint: disable=too-many-arguments

import json
from typing import Final, Literal
from uuid import UUID

import sqlalchemy
from aiohttp import web
from models_library.functions import (
    FunctionAccessRightsDB,
    FunctionClass,
    FunctionID,
    FunctionInputs,
    FunctionInputSchema,
    FunctionJobAccessRightsDB,
    FunctionJobClassSpecificData,
    FunctionJobCollectionAccessRightsDB,
    FunctionJobCollectionsListFilters,
    FunctionJobID,
    FunctionOutputs,
    FunctionOutputSchema,
    FunctionsApiAccessRights,
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
from sqlalchemy import Text, cast
from sqlalchemy.engine.row import Row
from sqlalchemy.ext.asyncio import AsyncConnection
from sqlalchemy.sql import func

from ..db.plugin import get_asyncpg_engine
from ..groups.api import list_all_user_groups_ids
from ..users.api import get_user_primary_group_id

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
    async with pass_or_acquire_connection(get_asyncpg_engine(app), connection) as conn:
        await check_user_api_access_rights(
            app,
            connection=conn,
            user_id=user_id,
            product_name=product_name,
            api_access_rights=[FunctionsApiAccessRights.WRITE_FUNCTIONS],
        )

        async with transaction_context(get_asyncpg_engine(app), conn) as transaction:
            result = await transaction.stream(
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
            row = await result.one()

            registered_function = RegisteredFunctionDB.model_validate(row)

        user_primary_group_id = await get_user_primary_group_id(app, user_id=user_id)
        await set_group_permissions(
            app,
            connection=conn,
            group_id=user_primary_group_id,
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
    async with pass_or_acquire_connection(get_asyncpg_engine(app), connection) as conn:
        await check_user_api_access_rights(
            app,
            connection=conn,
            user_id=user_id,
            product_name=product_name,
            api_access_rights=[
                FunctionsApiAccessRights.WRITE_FUNCTION_JOBS,
            ],
        )
        async with transaction_context(get_asyncpg_engine(app), conn) as transaction:
            result = await transaction.stream(
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
            row = await result.one()

            registered_function_job = RegisteredFunctionJobDB.model_validate(row)

    user_primary_group_id = await get_user_primary_group_id(app, user_id=user_id)
    await set_group_permissions(
        app,
        connection=conn,
        group_id=user_primary_group_id,
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
    async with pass_or_acquire_connection(get_asyncpg_engine(app), connection) as conn:
        await check_user_api_access_rights(
            app,
            connection=conn,
            user_id=user_id,
            product_name=product_name,
            api_access_rights=[
                FunctionsApiAccessRights.WRITE_FUNCTION_JOB_COLLECTIONS,
            ],
        )
        for job_id in job_ids:
            await check_user_permissions(
                app,
                connection=conn,
                user_id=user_id,
                product_name=product_name,
                object_type="function_job",
                object_id=job_id,
                permissions=["read"],
            )

        async with transaction_context(get_asyncpg_engine(app), conn) as transaction:
            result = await transaction.stream(
                function_job_collections_table.insert()
                .values(
                    title=title,
                    description=description,
                )
                .returning(*_FUNCTION_JOB_COLLECTIONS_TABLE_COLS)
            )
            row = await result.one_or_none()

            assert row is not None, (
                "No row was returned from the database after creating function job collection."
                f" Function job collection: {title}"
            )  # nosec

            function_job_collection_db = (
                RegisteredFunctionJobCollectionDB.model_validate(row)
            )
            job_collection_entries: list[Row] = []
            for job_id in job_ids:
                result = await transaction.stream(
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
                entry = await result.one_or_none()
                assert entry is not None, (
                    f"No row was returned from the database after creating function job collection entry {title}."
                    f" Job ID: {job_id}"
                )  # nosec
                job_collection_entries.append(entry)

        user_primary_group_id = await get_user_primary_group_id(app, user_id=user_id)
        await set_group_permissions(
            app,
            connection=conn,
            group_id=user_primary_group_id,
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
        await check_user_api_access_rights(
            app,
            connection=conn,
            user_id=user_id,
            product_name=product_name,
            api_access_rights=[FunctionsApiAccessRights.READ_FUNCTIONS],
        )

        result = await conn.stream(
            functions_table.select().where(functions_table.c.uuid == function_id)
        )
        row = await result.one_or_none()

        if row is None:
            raise FunctionIDNotFoundError(function_id=function_id)
        registered_function = RegisteredFunctionDB.model_validate(row)

        await check_user_permissions(
            app,
            connection=conn,
            user_id=user_id,
            product_name=product_name,
            object_id=function_id,
            object_type="function",
            permissions=["read"],
        )

    return registered_function


async def list_functions(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    user_id: UserID,
    product_name: ProductName,
    pagination_limit: int,
    pagination_offset: int,
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

        subquery = (
            functions_access_rights_table.select()
            .with_only_columns(functions_access_rights_table.c.function_uuid)
            .where(
                functions_access_rights_table.c.group_id.in_(user_groups),
                functions_access_rights_table.c.product_name == product_name,
                functions_access_rights_table.c.read,
            )
        )

        total_count_result = await conn.scalar(
            func.count()
            .select()
            .select_from(functions_table)
            .where(functions_table.c.uuid.in_(subquery))
        )
        result = await conn.stream(
            functions_table.select()
            .where(functions_table.c.uuid.in_(subquery))
            .offset(pagination_offset)
            .limit(pagination_limit)
        )
        rows = await result.all()
        if rows is None:
            return [], PageMetaInfoLimitOffset(
                total=0, offset=pagination_offset, limit=pagination_limit, count=0
            )

        return [
            RegisteredFunctionDB.model_validate(row) for row in rows
        ], PageMetaInfoLimitOffset(
            total=total_count_result,
            offset=pagination_offset,
            limit=pagination_limit,
            count=len(rows),
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

        total_count_result = await conn.scalar(
            func.count()
            .select()
            .select_from(function_jobs_table)
            .where(function_jobs_table.c.uuid.in_(access_subquery))
            .where(
                function_jobs_table.c.function_uuid == filter_by_function_id
                if filter_by_function_id
                else sqlalchemy.sql.true()
            )
        )
        result = await conn.stream(
            function_jobs_table.select()
            .where(function_jobs_table.c.uuid.in_(access_subquery))
            .where(
                function_jobs_table.c.function_uuid == filter_by_function_id
                if filter_by_function_id
                else sqlalchemy.sql.true()
            )
            .offset(pagination_offset)
            .limit(pagination_limit)
        )
        rows = await result.all()
        if rows is None:
            return [], PageMetaInfoLimitOffset(
                total=0, offset=pagination_offset, limit=pagination_limit, count=0
            )

        return [
            RegisteredFunctionJobDB.model_validate(dict(row)) for row in rows
        ], PageMetaInfoLimitOffset(
            total=total_count_result,
            offset=pagination_offset,
            limit=pagination_limit,
            count=len(rows),
        )


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
        query = function_job_collections_table.select().where(
            filter_and_access_condition
        )

        result = await conn.stream(
            query.offset(pagination_offset).limit(pagination_limit)
        )
        rows = await result.all()
        if rows is None:
            return [], PageMetaInfoLimitOffset(
                total=0, offset=pagination_offset, limit=pagination_limit, count=0
            )

        collections = []
        for row in rows:
            collection = RegisteredFunctionJobCollectionDB.model_validate(dict(row))
            job_result = await conn.stream(
                function_job_collections_to_function_jobs_table.select().where(
                    function_job_collections_to_function_jobs_table.c.function_job_collection_uuid
                    == row["uuid"]
                )
            )
            job_rows = await job_result.all()
            job_ids = (
                [job_row["function_job_uuid"] for job_row in job_rows]
                if job_rows
                else []
            )
            collections.append((collection, job_ids))
        return collections, PageMetaInfoLimitOffset(
            total=total_count_result,
            offset=pagination_offset,
            limit=pagination_limit,
            count=len(rows),
        )


async def delete_function(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    user_id: UserID,
    product_name: ProductName,
    function_id: FunctionID,
) -> None:
    async with pass_or_acquire_connection(get_asyncpg_engine(app), connection) as conn:
        await check_user_api_access_rights(
            app,
            connection=conn,
            user_id=user_id,
            product_name=product_name,
            api_access_rights=[
                FunctionsApiAccessRights.READ_FUNCTIONS,
                FunctionsApiAccessRights.WRITE_FUNCTIONS,
            ],
        )

        await check_user_permissions(
            app,
            connection=conn,
            user_id=user_id,
            product_name=product_name,
            object_id=function_id,
            object_type="function",
            permissions=["write"],
        )

        async with transaction_context(get_asyncpg_engine(app), conn) as transaction:
            # Check if the function exists
            result = await transaction.stream(
                functions_table.select().where(functions_table.c.uuid == function_id)
            )
            row = await result.one_or_none()

            if row is None:
                raise FunctionIDNotFoundError(function_id=function_id)

            # Proceed with deletion
            await transaction.execute(
                functions_table.delete().where(functions_table.c.uuid == function_id)
            )


async def update_function_title(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    user_id: UserID,
    product_name: ProductName,
    function_id: FunctionID,
    title: str,
) -> RegisteredFunctionDB:
    async with pass_or_acquire_connection(get_asyncpg_engine(app), connection) as conn:
        await check_user_api_access_rights(
            app,
            connection=conn,
            user_id=user_id,
            product_name=product_name,
            api_access_rights=[
                FunctionsApiAccessRights.READ_FUNCTIONS,
                FunctionsApiAccessRights.WRITE_FUNCTIONS,
            ],
        )

        await check_user_permissions(
            app,
            user_id=user_id,
            product_name=product_name,
            object_id=function_id,
            object_type="function",
            permissions=["write"],
        )

        async with transaction_context(get_asyncpg_engine(app), conn) as transaction:
            result = await transaction.stream(
                functions_table.update()
                .where(functions_table.c.uuid == function_id)
                .values(title=title)
                .returning(*_FUNCTIONS_TABLE_COLS)
            )
            row = await result.one_or_none()

            if row is None:
                raise FunctionIDNotFoundError(function_id=function_id)

            return RegisteredFunctionDB.model_validate(dict(row))


async def update_function_description(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    user_id: UserID,
    product_name: ProductName,
    function_id: FunctionID,
    description: str,
) -> RegisteredFunctionDB:
    async with pass_or_acquire_connection(get_asyncpg_engine(app), connection) as conn:
        await check_user_api_access_rights(
            app,
            connection=conn,
            user_id=user_id,
            product_name=product_name,
            api_access_rights=[
                FunctionsApiAccessRights.READ_FUNCTIONS,
                FunctionsApiAccessRights.WRITE_FUNCTIONS,
            ],
        )
        await check_user_permissions(
            app,
            conn,
            user_id=user_id,
            product_name=product_name,
            object_id=function_id,
            object_type="function",
            permissions=["write"],
        )

        async with transaction_context(get_asyncpg_engine(app), conn) as transaction:
            result = await transaction.stream(
                functions_table.update()
                .where(functions_table.c.uuid == function_id)
                .values(description=description)
                .returning(*_FUNCTIONS_TABLE_COLS)
            )
            row = await result.one_or_none()

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
        await check_user_api_access_rights(
            app,
            connection=conn,
            user_id=user_id,
            product_name=product_name,
            api_access_rights=[FunctionsApiAccessRights.READ_FUNCTION_JOBS],
        )
        await check_user_permissions(
            app,
            connection=conn,
            user_id=user_id,
            product_name=product_name,
            object_id=function_job_id,
            object_type="function_job",
            permissions=["read"],
        )

        async with transaction_context(get_asyncpg_engine(app), conn) as transaction:
            result = await transaction.stream(
                function_jobs_table.select().where(
                    function_jobs_table.c.uuid == function_job_id
                )
            )
            row = await result.one_or_none()

            if row is None:
                raise FunctionJobIDNotFoundError(function_job_id=function_job_id)

            return RegisteredFunctionJobDB.model_validate(dict(row))


async def delete_function_job(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    user_id: UserID,
    product_name: ProductName,
    function_job_id: FunctionID,
) -> None:
    async with pass_or_acquire_connection(get_asyncpg_engine(app), connection) as conn:
        await check_user_api_access_rights(
            app,
            connection=conn,
            user_id=user_id,
            product_name=product_name,
            api_access_rights=[
                FunctionsApiAccessRights.READ_FUNCTION_JOBS,
                FunctionsApiAccessRights.WRITE_FUNCTION_JOBS,
            ],
        )
        await check_user_permissions(
            app,
            connection=conn,
            user_id=user_id,
            product_name=product_name,
            object_id=function_job_id,
            object_type="function_job",
            permissions=["write"],
        )

        async with transaction_context(get_asyncpg_engine(app), conn) as transaction:
            # Check if the function job exists
            result = await transaction.stream(
                function_jobs_table.select().where(
                    function_jobs_table.c.uuid == function_job_id
                )
            )
            row = await result.one_or_none()
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
        await check_user_api_access_rights(
            app,
            connection=conn,
            user_id=user_id,
            product_name=product_name,
            api_access_rights=[FunctionsApiAccessRights.READ_FUNCTION_JOBS],
        )

        async with transaction_context(get_asyncpg_engine(app), conn) as transaction:
            result = await transaction.stream(
                function_jobs_table.select().where(
                    function_jobs_table.c.function_uuid == function_id,
                    cast(function_jobs_table.c.inputs, Text) == json.dumps(inputs),
                ),
            )
            rows = await result.all()

        if rows is None or len(rows) == 0:
            return None

        jobs: list[RegisteredFunctionJobDB] = []
        for row in rows:
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
        await check_user_api_access_rights(
            app,
            connection=conn,
            user_id=user_id,
            product_name=product_name,
            api_access_rights=[FunctionsApiAccessRights.READ_FUNCTION_JOB_COLLECTIONS],
        )
        await check_user_permissions(
            app,
            connection=conn,
            user_id=user_id,
            product_name=product_name,
            object_id=function_job_collection_id,
            object_type="function_job_collection",
            permissions=["read"],
        )

        result = await conn.stream(
            function_job_collections_table.select().where(
                function_job_collections_table.c.uuid == function_job_collection_id
            )
        )
        row = await result.one_or_none()

        if row is None:
            raise FunctionJobCollectionIDNotFoundError(
                function_job_collection_id=function_job_collection_id
            )

        # Retrieve associated job ids from the join table
        job_result = await conn.stream(
            function_job_collections_to_function_jobs_table.select().where(
                function_job_collections_to_function_jobs_table.c.function_job_collection_uuid
                == row["uuid"]
            )
        )
        job_rows = await job_result.all()

        job_ids = (
            [job_row["function_job_uuid"] for job_row in job_rows] if job_rows else []
        )

        job_collection = RegisteredFunctionJobCollectionDB.model_validate(dict(row))

    return job_collection, job_ids


async def delete_function_job_collection(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    user_id: UserID,
    product_name: ProductName,
    function_job_collection_id: FunctionID,
) -> None:
    async with pass_or_acquire_connection(get_asyncpg_engine(app), connection) as conn:
        await check_user_api_access_rights(
            app,
            connection=conn,
            user_id=user_id,
            product_name=product_name,
            api_access_rights=[
                FunctionsApiAccessRights.READ_FUNCTION_JOB_COLLECTIONS,
                FunctionsApiAccessRights.WRITE_FUNCTION_JOB_COLLECTIONS,
            ],
        )
        await check_user_permissions(
            app,
            connection=conn,
            user_id=user_id,
            product_name=product_name,
            object_id=function_job_collection_id,
            object_type="function_job_collection",
            permissions=["write"],
        )

        async with transaction_context(get_asyncpg_engine(app), conn) as transaction:
            # Check if the function job collection exists
            result = await transaction.stream(
                function_job_collections_table.select().where(
                    function_job_collections_table.c.uuid == function_job_collection_id
                )
            )
            row = await result.one_or_none()
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
    group_id: GroupID,
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
            result = await transaction.stream(
                access_rights_table.select().where(
                    getattr(access_rights_table.c, field_name) == object_id,
                    access_rights_table.c.group_id == group_id,
                )
            )
            row = await result.one_or_none()

            if row is None:
                # Insert new access rights if the group does not have any
                await transaction.execute(
                    access_rights_table.insert().values(
                        **{field_name: object_id},
                        group_id=group_id,
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
                        access_rights_table.c.group_id == group_id,
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

        result = await conn.stream(
            funcapi_api_access_rights_table.select().where(
                funcapi_api_access_rights_table.c.group_id.in_(user_groups),
                funcapi_api_access_rights_table.c.product_name == product_name,
            )
        )
        rows = await result.all()
        if not rows:
            return FunctionUserApiAccessRights(user_id=user_id)
        combined_permissions = {
            "read_functions": any(row["read_functions"] for row in rows),
            "write_functions": any(row["write_functions"] for row in rows),
            "execute_functions": any(row["execute_functions"] for row in rows),
            "read_function_jobs": any(row["read_function_jobs"] for row in rows),
            "write_function_jobs": any(row["write_function_jobs"] for row in rows),
            "execute_function_jobs": any(row["execute_function_jobs"] for row in rows),
            "read_function_job_collections": any(
                row["read_function_job_collections"] for row in rows
            ),
            "write_function_job_collections": any(
                row["write_function_job_collections"] for row in rows
            ),
            "execute_function_job_collections": any(
                row["execute_function_job_collections"] for row in rows
            ),
            "user_id": user_id,
        }
        return FunctionUserApiAccessRights.model_validate(combined_permissions)


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

        # Combine permissions for all groups the user belongs to
        result = await conn.stream(
            access_rights_table.select()
            .with_only_columns(cols)
            .where(
                getattr(access_rights_table.c, f"{object_type}_uuid") == object_id,
                access_rights_table.c.product_name == product_name,
                access_rights_table.c.group_id.in_(user_groups),
            )
        )
        rows = await result.all()

        if not rows:
            return None

        # Combine permissions across all rows
        combined_permissions = {
            "read": any(row["read"] for row in rows),
            "write": any(row["write"] for row in rows),
            "execute": any(row["execute"] for row in rows),
        }

        return FunctionAccessRightsDB.model_validate(combined_permissions)


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
        result = await conn.stream(
            main_table.select().where(main_table.c.uuid == object_id)
        )
        row = await result.one_or_none()

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
            raise _ERRORS_MAP[api_access_right]

    return True
