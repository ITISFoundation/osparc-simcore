# pylint: disable=too-many-arguments

import json
import logging

import sqlalchemy
from aiohttp import web
from models_library.functions import (
    BatchCreateRegisteredFunctionJobsDB,
    BatchUpdateRegisteredFunctionJobsDB,
    FunctionClass,
    FunctionClassSpecificData,
    FunctionID,
    FunctionInputsList,
    FunctionJobCollectionID,
    FunctionJobDB,
    FunctionJobID,
    FunctionJobPatchRequest,
    FunctionJobStatus,
    FunctionOutputs,
    FunctionsApiAccessRights,
    RegisteredFunctionJobDB,
    RegisteredFunctionJobPatch,
    RegisteredFunctionJobWithStatusDB,
)
from models_library.functions_errors import (
    FunctionJobIDNotFoundError,
    FunctionJobPatchModelIncompatibleError,
    UnsupportedFunctionJobClassError,
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
from sqlalchemy import Text, cast, func
from sqlalchemy.ext.asyncio import AsyncConnection

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

_logger = logging.getLogger(__name__)


async def create_function_jobs(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    user_id: UserID,
    product_name: ProductName,
    function_jobs: list[FunctionJobDB],
) -> BatchCreateRegisteredFunctionJobsDB:
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

        # Prepare values for batch insert
        values_to_insert = [
            {
                "function_uuid": job.function_uuid,
                "inputs": job.inputs,
                "outputs": job.outputs,
                "function_class": job.function_class,
                "class_specific_data": job.class_specific_data,
                "title": job.title,
                "description": job.description,
                "status": "created",
            }
            for job in function_jobs
        ]

        # Batch insert all function jobs in a single query
        result = await transaction.execute(
            function_jobs_table.insert().values(values_to_insert).returning(*_FUNCTION_JOBS_TABLE_COLS)
        )

        # Get all created jobs
        created_jobs = TypeAdapter(list[RegisteredFunctionJobDB]).validate_python(list(result))

        # Get user primary group and set permissions for all jobs
        user_primary_group_id = await users_service.get_user_primary_group_id(app, user_id=user_id)
        job_uuids = [job.uuid for job in created_jobs]

        await _internal_set_group_permissions(
            app,
            connection=transaction,
            permission_group_id=user_primary_group_id,
            product_name=product_name,
            object_type="function_job",
            object_ids=job_uuids,
            read=True,
            write=True,
            execute=True,
        )

    return BatchCreateRegisteredFunctionJobsDB(created_items=created_jobs)


async def patch_function_jobs(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    user_id: UserID,
    product_name: ProductName,
    function_job_patch_requests: list[FunctionJobPatchRequest],
) -> BatchUpdateRegisteredFunctionJobsDB:
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
        updated_jobs = []
        for patch_request in function_job_patch_requests:
            job = await get_function_job(
                app,
                connection=transaction,
                user_id=user_id,
                product_name=product_name,
                function_job_id=patch_request.uid,
            )
            if job.function_class != patch_request.patch.function_class:
                raise FunctionJobPatchModelIncompatibleError(function_id=job.function_uuid, product_name=product_name)

            class_specific_data = _update_class_specific_data(
                class_specific_data=job.class_specific_data, patch=patch_request.patch
            )
            update_values = {
                "inputs": patch_request.patch.inputs,
                "outputs": patch_request.patch.outputs,
                "class_specific_data": class_specific_data,
                "title": patch_request.patch.title,
                "description": patch_request.patch.description,
            }

            result = await transaction.execute(
                function_jobs_table.update()
                .where(function_jobs_table.c.uuid == f"{patch_request.uid}")
                .values(**{k: v for k, v in update_values.items() if v is not None})
                .returning(*_FUNCTION_JOBS_TABLE_COLS)
            )
            updated_jobs.append(RegisteredFunctionJobDB.model_validate(result.one()))

        return BatchUpdateRegisteredFunctionJobsDB(updated_items=updated_jobs)


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
                .with_only_columns(function_job_collections_to_function_jobs_table.c.function_job_uuid)
                .where(
                    function_job_collections_to_function_jobs_table.c.function_job_collection_uuid
                    == filter_by_function_job_collection_id
                )
                .order_by(
                    function_job_collections_to_function_jobs_table.c.order,
                    function_job_collections_to_function_jobs_table.c.function_job_uuid,
                )
            )
            filter_conditions = sqlalchemy.and_(
                filter_conditions,
                function_jobs_table.c.uuid.in_(collection_subquery),
            )

        total_count_result = await conn.scalar(
            func.count().select().select_from(function_jobs_table).where(filter_conditions)
        )
        if total_count_result == 0:
            return [], PageMetaInfoLimitOffset(total=0, offset=pagination_offset, limit=pagination_limit, count=0)
        results = [
            RegisteredFunctionJobWithStatusDB.model_validate(row)
            async for row in await conn.stream(
                function_jobs_table.select().where(filter_conditions).offset(pagination_offset).limit(pagination_limit)
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
            function_jobs_table.select().where(function_jobs_table.c.uuid == function_job_id)
        )
        row = result.one_or_none()
        if row is None:
            raise FunctionJobIDNotFoundError(function_job_id=function_job_id)

        # Proceed with deletion
        await transaction.execute(function_jobs_table.delete().where(function_jobs_table.c.uuid == function_job_id))


async def find_cached_function_jobs(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    user_id: UserID,
    function_id: FunctionID,
    product_name: ProductName,
    inputs: FunctionInputsList,
    cached_job_statuses: list[FunctionJobStatus] | None = None,
) -> list[RegisteredFunctionJobDB | None]:
    async with pass_or_acquire_connection(get_asyncpg_engine(app), connection) as conn:
        # Get user groups for access check
        user_groups = await list_all_user_groups_ids(app, user_id=user_id)

        # Create access subquery
        access_subquery = (
            function_jobs_access_rights_table.select()
            .with_only_columns(function_jobs_access_rights_table.c.function_job_uuid)
            .where(
                function_jobs_access_rights_table.c.group_id.in_(user_groups),
                function_jobs_access_rights_table.c.product_name == product_name,
                function_jobs_access_rights_table.c.read,
            )
        )

        # Create list of JSON dumped inputs for comparison
        json_inputs = [json.dumps(inp) for inp in inputs]

        # Build filter conditions
        filter_conditions = sqlalchemy.and_(
            function_jobs_table.c.function_uuid == function_id,
            cast(function_jobs_table.c.inputs, Text).in_(json_inputs),
            function_jobs_table.c.uuid.in_(access_subquery),
            (
                function_jobs_table.c.status.in_([status.status for status in cached_job_statuses])
                if cached_job_statuses is not None
                else sqlalchemy.sql.true()
            ),
        )

        # Use DISTINCT ON to get only one job per input (the most recent one)
        results = await conn.execute(
            function_jobs_table.select()
            .distinct(cast(function_jobs_table.c.inputs, Text))
            .where(filter_conditions)
            .order_by(
                cast(function_jobs_table.c.inputs, Text),
                function_jobs_table.c.created.desc(),
            )
        )

        # Create a mapping from JSON inputs to jobs
        _ensure_str = lambda x: x if isinstance(x, str) else json.dumps(x)
        jobs_by_input: dict[str, RegisteredFunctionJobDB] = {
            _ensure_str(row.inputs): RegisteredFunctionJobDB.model_validate(row) for row in results
        }

        return [jobs_by_input.get(input_) for input_ in json_inputs]


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

        result = await conn.execute(function_jobs_table.select().where(function_jobs_table.c.uuid == function_job_id))
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

        result = await conn.execute(function_jobs_table.select().where(function_jobs_table.c.uuid == function_job_id))
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

        result = await conn.execute(function_jobs_table.select().where(function_jobs_table.c.uuid == function_job_id))
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


def _update_class_specific_data(
    class_specific_data: dict,
    patch: RegisteredFunctionJobPatch,
) -> FunctionClassSpecificData:
    if patch.function_class == FunctionClass.PROJECT:
        return FunctionClassSpecificData(
            project_job_id=(
                f"{patch.project_job_id}" if patch.project_job_id else class_specific_data.get("project_job_id")
            ),
            job_creation_task_id=(
                f"{patch.job_creation_task_id}"
                if patch.job_creation_task_id
                else class_specific_data.get("job_creation_task_id")
            ),
        )
    if patch.function_class == FunctionClass.SOLVER:
        return FunctionClassSpecificData(
            solver_job_id=(
                f"{patch.solver_job_id}" if patch.solver_job_id else class_specific_data.get("solver_job_id")
            ),
            job_creation_task_id=(
                f"{patch.job_creation_task_id}"
                if patch.job_creation_task_id
                else class_specific_data.get("job_creation_task_id")
            ),
        )
    raise UnsupportedFunctionJobClassError(function_job_class=patch.function_class)
