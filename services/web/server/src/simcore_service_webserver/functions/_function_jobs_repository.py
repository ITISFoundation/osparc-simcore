import json

import sqlalchemy
from aiohttp import web
from models_library.functions import (
    FunctionClass,
    FunctionID,
    FunctionInputs,
    FunctionJobClassSpecificData,
    FunctionJobCollectionID,
    FunctionJobID,
    FunctionJobStatus,
    FunctionOutputs,
    FunctionsApiAccessRights,
    RegisteredFunctionJobDB,
    RegisteredFunctionJobWithStatusDB,
)
from models_library.functions_errors import (
    FunctionJobIDNotFoundError,
    FunctionJobReadAccessDeniedError,
)
from models_library.products import ProductName
from models_library.rest_pagination import PageMetaInfoLimitOffset
from models_library.users import UserID
from pydantic import TypeAdapter
from simcore_postgres_database.models.funcapi_function_job_collections_to_function_jobs_table import (
    function_job_collections_to_function_jobs_table,
)
from simcore_postgres_database.models.funcapi_function_jobs_access_rights_table import (
    function_jobs_access_rights_table,
)
from simcore_postgres_database.models.funcapi_function_jobs_table import (
    function_jobs_table,
)
from simcore_postgres_database.utils_repos import (
    pass_or_acquire_connection,
    transaction_context,
)
from sqlalchemy import Text, cast
from sqlalchemy.ext.asyncio import AsyncConnection
from sqlalchemy.sql import func

from ..db.plugin import get_asyncpg_engine
from ..groups.api import list_all_user_groups_ids
from ..users import users_service
from ._functions_permissions_repository import (
    _internal_set_group_permissions,
    check_user_api_access_rights,
    check_user_permissions,
)
from ._functions_table_cols import (
    _FUNCTION_JOBS_TABLE_COLS,
)


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


async def patch_function_job(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    user_id: UserID,
    product_name: ProductName,
    registered_function_job_db: RegisteredFunctionJobDB,
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
            function_jobs_table.update()
            .where(function_jobs_table.c.uuid == f"{registered_function_job_db.uuid}")
            .values(
                inputs=registered_function_job_db.inputs,
                outputs=registered_function_job_db.outputs,
                function_class=registered_function_job_db.function_class,
                class_specific_data=registered_function_job_db.class_specific_data,
                title=registered_function_job_db.title,
                description=registered_function_job_db.description,
                status="created",
            )
            .returning(*_FUNCTION_JOBS_TABLE_COLS)
        )
        row = result.one()

        return RegisteredFunctionJobDB.model_validate(row)


async def list_function_jobs_with_status(
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
) -> tuple[list[RegisteredFunctionJobWithStatusDB], PageMetaInfoLimitOffset]:
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
            RegisteredFunctionJobWithStatusDB.model_validate(row)
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


async def update_function_job_status(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    function_job_id: FunctionJobID,
    job_status: FunctionJobStatus,
) -> FunctionJobStatus:
    async with transaction_context(get_asyncpg_engine(app), connection) as transaction:
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
    function_job_id: FunctionJobID,
    outputs: FunctionOutputs,
) -> FunctionOutputs:
    async with transaction_context(get_asyncpg_engine(app), connection) as transaction:
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
