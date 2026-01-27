import sqlalchemy
from aiohttp import web
from models_library.functions import (
    FunctionID,
    FunctionJobCollectionsListFilters,
    FunctionJobID,
    FunctionsApiAccessRights,
    RegisteredFunctionJobCollectionDB,
)
from models_library.functions_errors import FunctionJobCollectionIDNotFoundError
from models_library.products import ProductName
from models_library.rest_pagination import PageMetaInfoLimitOffset
from models_library.users import UserID
from pydantic import TypeAdapter
from simcore_postgres_database.models.funcapi_function_job_collections_access_rights_table import (
    function_job_collections_access_rights_table,
)
from simcore_postgres_database.models.funcapi_function_job_collections_table import (
    function_job_collections_table,
)
from simcore_postgres_database.models.funcapi_function_job_collections_to_function_jobs_table import (
    function_job_collections_to_function_jobs_table,
)
from simcore_postgres_database.models.funcapi_function_jobs_table import (
    function_jobs_table,
)
from simcore_postgres_database.utils_repos import (
    pass_or_acquire_connection,
    transaction_context,
)
from sqlalchemy.engine.row import Row
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
    _FUNCTION_JOB_COLLECTIONS_TABLE_COLS,
)


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

        function_job_collection_db = RegisteredFunctionJobCollectionDB.model_validate(row)
        job_collection_entries: list[Row] = []
        for order, job_id in enumerate(job_ids, 1):
            result = await transaction.execute(
                function_job_collections_to_function_jobs_table.insert()
                .values(
                    function_job_collection_uuid=function_job_collection_db.uuid,
                    function_job_uuid=job_id,
                    order=order,
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

        user_primary_group_id = await users_service.get_user_primary_group_id(app, user_id=user_id)
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

    return function_job_collection_db, [entry.function_job_uuid for entry in job_collection_entries]


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
            function_id = TypeAdapter(FunctionID).validate_python(filters.has_function_id)
            subquery = (
                function_job_collections_to_function_jobs_table.select()
                .with_only_columns(
                    func.distinct(function_job_collections_to_function_jobs_table.c.function_job_collection_uuid)
                )
                .join(
                    function_jobs_table,
                    function_job_collections_to_function_jobs_table.c.function_job_uuid == function_jobs_table.c.uuid,
                )
                .where(function_jobs_table.c.function_uuid == function_id)
            )
            filter_condition = function_job_collections_table.c.uuid.in_(subquery)
        user_groups = await list_all_user_groups_ids(app, user_id=user_id)

        access_subquery = (
            function_job_collections_access_rights_table.select()
            .with_only_columns(function_job_collections_access_rights_table.c.function_job_collection_uuid)
            .where(
                function_job_collections_access_rights_table.c.group_id.in_(user_groups),
                function_job_collections_access_rights_table.c.product_name == product_name,
                function_job_collections_access_rights_table.c.read,
            )
        )

        filter_and_access_condition = sqlalchemy.and_(
            filter_condition,
            function_job_collections_table.c.uuid.in_(access_subquery),
        )

        total_count_result = await conn.scalar(
            func.count().select().select_from(function_job_collections_table).where(filter_and_access_condition)
        )
        if total_count_result == 0:
            return [], PageMetaInfoLimitOffset(total=0, offset=pagination_offset, limit=pagination_limit, count=0)

        query = function_job_collections_table.select().where(filter_and_access_condition)

        collections = []
        async for row in await conn.stream(query.offset(pagination_offset).limit(pagination_limit)):
            collection = RegisteredFunctionJobCollectionDB.model_validate(row)
            job_ids = [
                job_row.function_job_uuid
                async for job_row in await conn.stream(
                    function_job_collections_to_function_jobs_table.select()
                    .where(function_job_collections_to_function_jobs_table.c.function_job_collection_uuid == row.uuid)
                    .order_by(
                        function_job_collections_to_function_jobs_table.c.order,
                        function_job_collections_to_function_jobs_table.c.function_job_uuid,
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
            raise FunctionJobCollectionIDNotFoundError(function_job_collection_id=function_job_collection_id)

        # Retrieve associated job ids from the join table
        job_ids = [
            job_row.function_job_uuid
            async for job_row in await conn.stream(
                function_job_collections_to_function_jobs_table.select()
                .where(function_job_collections_to_function_jobs_table.c.function_job_collection_uuid == row.uuid)
                .order_by(
                    function_job_collections_to_function_jobs_table.c.order,
                    function_job_collections_to_function_jobs_table.c.function_job_uuid,
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
            raise FunctionJobCollectionIDNotFoundError(function_job_collection_id=function_job_collection_id)
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
