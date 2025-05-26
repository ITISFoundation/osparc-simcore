import json

import sqlalchemy
from aiohttp import web
from models_library.functions import (
    FunctionAccessRightsDB,
    FunctionClass,
    FunctionID,
    FunctionIDNotFoundError,
    FunctionInputs,
    FunctionInputSchema,
    FunctionJobAccessRightsDB,
    FunctionJobClassSpecificData,
    FunctionJobCollectionAccessRightsDB,
    FunctionJobCollectionIDNotFoundError,
    FunctionJobCollectionsListFilters,
    FunctionJobID,
    FunctionJobIDNotFoundError,
    FunctionOutputs,
    FunctionOutputSchema,
    FunctionReadAccessDeniedError,
    RegisteredFunctionDB,
    RegisteredFunctionJobCollectionDB,
    RegisteredFunctionJobDB,
)
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
from simcore_postgres_database.models.funcapi_functions_access_rights_table import (
    functions_access_rights_table,
)
from simcore_postgres_database.models.funcapi_functions_table import functions_table
from simcore_postgres_database.utils_repos import (
    get_columns_from_db_model,
    transaction_context,
)
from sqlalchemy import Text, cast
from sqlalchemy.ext.asyncio import AsyncConnection
from sqlalchemy.sql import func

from ..db.plugin import get_asyncpg_engine

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
_FUNCTION_JOB_COLLECTIONS_ACCESS_RIGHTS_TABLE_COLS = get_columns_from_db_model(
    function_job_collections_access_rights_table, FunctionJobAccessRightsDB
)
_FUNCTION_JOB_COLLECTIONS_ACCESS_RIGHTS_TABLE_COLS = get_columns_from_db_model(
    function_job_collections_access_rights_table, FunctionJobCollectionAccessRightsDB
)


async def create_function(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    user_id: UserID,
    function_class: FunctionClass,
    class_specific_data: dict,
    title: str,
    description: str,
    input_schema: FunctionInputSchema,
    output_schema: FunctionOutputSchema,
    default_inputs: FunctionInputs,
) -> RegisteredFunctionDB:

    async with transaction_context(get_asyncpg_engine(app), connection) as conn:
        result = await conn.stream(
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

        registered_function = RegisteredFunctionDB.model_validate(dict(row))

        await set_user_permissions_for_function_ids(
            app,
            connection=connection,
            user_id=user_id,
            function_ids=[registered_function.uuid],
            read=True,
            write=True,
            execute=True,
        )

        return RegisteredFunctionDB.model_validate(dict(row))


async def create_function_job(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    user_id: UserID,
    function_class: FunctionClass,
    function_uid: FunctionID,
    title: str,
    description: str,
    inputs: FunctionInputs,
    outputs: FunctionOutputs,
    class_specific_data: FunctionJobClassSpecificData,
) -> RegisteredFunctionJobDB:

    async with transaction_context(get_asyncpg_engine(app), connection) as conn:
        result = await conn.stream(
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

        await result.one()

        return RegisteredFunctionJobDB.model_validate(dict(row))


async def create_function_job_collection(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    user_id: UserID,
    title: str,
    description: str,
    job_ids: list[FunctionJobID],
) -> tuple[RegisteredFunctionJobCollectionDB, list[FunctionJobID]]:
    async with transaction_context(get_asyncpg_engine(app), connection) as conn:
        result = await conn.stream(
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

        function_job_collection_db = RegisteredFunctionJobCollectionDB.model_validate(
            dict(row)
        )
        job_collection_entries = []
        for job_id in job_ids:
            result = await conn.stream(
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
            job_collection_entries.append(dict(entry))

        return function_job_collection_db, [
            dict(entry)["function_job_uuid"] for entry in job_collection_entries
        ]


async def get_function(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    user_id: UserID,
    function_id: FunctionID,
) -> RegisteredFunctionDB:

    user_permission = await get_user_permissions_for_function_id(
        app, connection=connection, user_id=user_id, function_id=function_id
    )
    if user_permission is None or not user_permission.read:
        raise FunctionReadAccessDeniedError(function_id=function_id, user_id=user_id)

    async with transaction_context(get_asyncpg_engine(app), connection) as conn:
        result = await conn.stream(
            functions_table.select().where(functions_table.c.uuid == function_id)
        )
        row = await result.one_or_none()

        if row is None:
            raise FunctionIDNotFoundError(function_id=function_id)
        return RegisteredFunctionDB.model_validate(dict(row))


async def list_functions(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    user_id: UserID,
    pagination_limit: int,
    pagination_offset: int,
) -> tuple[list[RegisteredFunctionDB], PageMetaInfoLimitOffset]:

    async with transaction_context(get_asyncpg_engine(app), connection) as conn:
        # Filter functions by user read access
        subquery = (
            functions_access_rights_table.select()
            .with_only_columns(functions_access_rights_table.c.function_uuid)
            .where(
                functions_access_rights_table.c.user_id == user_id,
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
            RegisteredFunctionDB.model_validate(dict(row)) for row in rows
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
    pagination_limit: int,
    pagination_offset: int,
    filter_by_function_id: FunctionID | None = None,
) -> tuple[list[RegisteredFunctionJobDB], PageMetaInfoLimitOffset]:

    async with transaction_context(get_asyncpg_engine(app), connection) as conn:
        total_count_result = await conn.scalar(
            func.count()
            .select()
            .select_from(function_jobs_table)
            .where(
                (
                    function_jobs_table.c.function_uuid == filter_by_function_id
                    if filter_by_function_id
                    else True
                ),
            )
        )
        result = await conn.stream(
            function_jobs_table.select()
            .offset(pagination_offset)
            .limit(pagination_limit)
            .where(
                (
                    function_jobs_table.c.function_uuid == filter_by_function_id
                    if filter_by_function_id
                    else True
                ),
            )
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

    async with transaction_context(get_asyncpg_engine(app), connection) as conn:
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
        total_count_result = await conn.scalar(
            func.count()
            .select()
            .select_from(function_job_collections_table)
            .where(filter_condition)
        )
        query = function_job_collections_table.select().where(filter_condition)

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
    function_id: FunctionID,
) -> None:

    async with transaction_context(get_asyncpg_engine(app), connection) as conn:
        # Check if the function exists
        result = await conn.stream(
            functions_table.select().where(functions_table.c.uuid == function_id)
        )
        row = await result.one_or_none()

        if row is None:
            raise FunctionIDNotFoundError(function_id=function_id)

        # Proceed with deletion
        await conn.execute(
            functions_table.delete().where(functions_table.c.uuid == function_id)
        )


async def update_function_title(
    app: web.Application, *, user_id: UserID, function_id: FunctionID, title: str
) -> RegisteredFunctionDB:
    async with transaction_context(get_asyncpg_engine(app)) as conn:
        result = await conn.stream(
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
    app: web.Application, *, user_id: UserID, function_id: FunctionID, description: str
) -> RegisteredFunctionDB:
    async with transaction_context(get_asyncpg_engine(app)) as conn:
        result = await conn.stream(
            functions_table.update()
            .where(functions_table.c.uuid == function_id)
            .values(description=description)
            .returning(*_FUNCTIONS_TABLE_COLS)
        )
        row = await result.one_or_none()

        if row is None:
            raise FunctionIDNotFoundError(function_id=function_id)

        return RegisteredFunctionDB.model_validate(dict(row))


async def get_function_job(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    user_id: UserID,
    function_job_id: FunctionID,
) -> RegisteredFunctionJobDB:

    async with transaction_context(get_asyncpg_engine(app), connection) as conn:
        result = await conn.stream(
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
    function_job_id: FunctionID,
) -> None:
    async with transaction_context(get_asyncpg_engine(app), connection) as conn:
        # Check if the function job exists
        result = await conn.stream(
            function_jobs_table.select().where(
                function_jobs_table.c.uuid == function_job_id
            )
        )
        row = await result.one_or_none()
        if row is None:
            raise FunctionJobIDNotFoundError(function_job_id=function_job_id)

        # Proceed with deletion
        await conn.execute(
            function_jobs_table.delete().where(
                function_jobs_table.c.uuid == function_job_id
            )
        )


async def find_cached_function_job(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    user_id: UserID,
    function_id: FunctionID,
    inputs: FunctionInputs,
) -> RegisteredFunctionJobDB | None:

    async with transaction_context(get_asyncpg_engine(app), connection) as conn:
        result = await conn.stream(
            function_jobs_table.select().where(
                function_jobs_table.c.function_uuid == function_id,
                cast(function_jobs_table.c.inputs, Text) == json.dumps(inputs),
            ),
        )

        rows = await result.all()

        if rows is None or len(rows) == 0:
            return None

        assert len(rows) == 1, (
            "More than one function job found with the same function id and inputs."
            f" Function id: {function_id}, Inputs: {inputs}"
        )  # nosec

        row = rows[0]

        job = RegisteredFunctionJobDB.model_validate(dict(row))
        if job.inputs == inputs:
            return job

        return None


async def get_function_job_collection(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    user_id: UserID,
    function_job_collection_id: FunctionID,
) -> tuple[RegisteredFunctionJobCollectionDB, list[FunctionJobID]]:

    async with transaction_context(get_asyncpg_engine(app), connection) as conn:
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
    function_job_collection_id: FunctionID,
) -> None:

    async with transaction_context(get_asyncpg_engine(app), connection) as conn:
        # Check if the function job collection exists
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
        # Proceed with deletion
        await conn.execute(
            function_job_collections_table.delete().where(
                function_job_collections_table.c.uuid == function_job_collection_id
            )
        )
        await conn.execute(
            function_job_collections_to_function_jobs_table.delete().where(
                function_job_collections_to_function_jobs_table.c.function_job_collection_uuid
                == function_job_collection_id
            )
        )


async def set_user_permissions_for_function_ids(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    user_id: UserID,
    function_ids: list[FunctionID],
    read: bool | None = None,
    write: bool | None = None,
    execute: bool | None = None,
) -> None:

    async with transaction_context(get_asyncpg_engine(app), connection) as conn:
        for function_id in function_ids:
            # Check if the user already has access rights for the function
            result = await conn.stream(
                functions_access_rights_table.select().where(
                    functions_access_rights_table.c.function_uuid == function_id,
                    functions_access_rights_table.c.user_id == user_id,
                )
            )
            row = await result.one_or_none()

            if row is None:
                # Insert new access rights if the user does not have any
                await conn.execute(
                    functions_access_rights_table.insert().values(
                        function_uuid=function_id,
                        user_id=user_id,
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

                await conn.execute(
                    functions_access_rights_table.update()
                    .where(
                        functions_access_rights_table.c.function_uuid == function_id,
                        functions_access_rights_table.c.user_id == user_id,
                    )
                    .values(**update_values)
                )


async def get_user_permissions_for_function_id(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    user_id: UserID,
    function_id: FunctionID,
) -> FunctionAccessRightsDB | None:
    async with transaction_context(get_asyncpg_engine(app), connection) as conn:
        result = await conn.stream(
            functions_access_rights_table.select().where(
                functions_access_rights_table.c.user_id == user_id,
                functions_access_rights_table.c.function_uuid == function_id,
            )
        )
        row = await result.one_or_none()
        return FunctionAccessRightsDB.model_validate(dict(row)) if row else None
