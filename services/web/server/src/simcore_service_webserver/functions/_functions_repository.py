import json

from aiohttp import web
from models_library.api_schemas_webserver.functions_wb_schema import (
    FunctionDB,
    FunctionID,
    FunctionInputs,
    FunctionJobCollection,
    FunctionJobCollectionDB,
    FunctionJobDB,
    FunctionJobID,
)
from simcore_postgres_database.models.functions_models_db import (
    function_job_collections as function_job_collections_table,
)
from simcore_postgres_database.models.functions_models_db import (
    function_job_collections_to_function_jobs as function_job_collections_to_function_jobs_table,
)
from simcore_postgres_database.models.functions_models_db import (
    function_jobs as function_jobs_table,
)
from simcore_postgres_database.models.functions_models_db import (
    functions as functions_table,
)
from simcore_postgres_database.utils_repos import (
    get_columns_from_db_model,
    transaction_context,
)
from sqlalchemy import Text, cast
from sqlalchemy.ext.asyncio import AsyncConnection

from ..db.plugin import get_asyncpg_engine

_FUNCTIONS_TABLE_COLS = get_columns_from_db_model(functions_table, FunctionDB)
_FUNCTION_JOBS_TABLE_COLS = get_columns_from_db_model(
    function_jobs_table, FunctionJobDB
)
_FUNCTION_JOB_COLLECTIONS_TABLE_COLS = get_columns_from_db_model(
    function_job_collections_table, FunctionJobCollectionDB
)


async def register_function(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    function: FunctionDB,
) -> FunctionDB:

    if function.uuid is not None:
        msg = "Function uid is not None. Cannot register function."
        raise ValueError(msg)

    async with transaction_context(get_asyncpg_engine(app), connection) as conn:
        result = await conn.stream(
            functions_table.insert()
            .values(
                title=function.title,
                description=function.description,
                input_schema=(
                    function.input_schema.model_dump()
                    if function.input_schema is not None
                    else None
                ),
                output_schema=(
                    function.output_schema.model_dump()
                    if function.output_schema is not None
                    else None
                ),
                function_class=function.function_class,
                class_specific_data=function.class_specific_data,
                default_inputs=function.default_inputs,
            )
            .returning(*_FUNCTIONS_TABLE_COLS)
        )
        row = await result.first()

        if row is None:
            msg = "No row was returned from the database after creating function."
            raise ValueError(msg)

        return FunctionDB.model_validate(dict(row))


async def get_function(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    function_id: FunctionID,
) -> FunctionDB:

    async with transaction_context(get_asyncpg_engine(app), connection) as conn:
        result = await conn.stream(
            functions_table.select().where(functions_table.c.uuid == function_id)
        )
        row = await result.first()

        if row is None:
            msg = f"No function found with id {function_id}."
            raise web.HTTPNotFound(reason=msg)

        return FunctionDB.model_validate(dict(row))


async def list_functions(
    app: web.Application,
    connection: AsyncConnection | None = None,
) -> list[FunctionDB]:

    async with transaction_context(get_asyncpg_engine(app), connection) as conn:
        result = await conn.stream(functions_table.select().where())
        rows = await result.all()
        if rows is None:
            return []

        return [FunctionDB.model_validate(dict(row)) for row in rows]


async def delete_function(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    function_id: FunctionID,
) -> None:

    async with transaction_context(get_asyncpg_engine(app), connection) as conn:
        await conn.execute(
            functions_table.delete().where(functions_table.c.uuid == function_id)
        )


async def register_function_job(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    function_job: FunctionJobDB,
) -> FunctionJobDB:

    async with transaction_context(get_asyncpg_engine(app), connection) as conn:
        result = await conn.stream(
            function_jobs_table.insert()
            .values(
                function_uuid=function_job.function_uuid,
                inputs=function_job.inputs,
                outputs=function_job.outputs,
                function_class=function_job.function_class,
                class_specific_data=function_job.class_specific_data,
                title=function_job.title,
                status="created",
            )
            .returning(*_FUNCTION_JOBS_TABLE_COLS)
        )
        row = await result.first()

        if row is None:
            msg = "No row was returned from the database after creating function job."
            raise ValueError(msg)

        return FunctionJobDB.model_validate(dict(row))


async def get_function_job(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    function_job_id: FunctionID,
) -> FunctionJobDB:

    async with transaction_context(get_asyncpg_engine(app), connection) as conn:
        result = await conn.stream(
            function_jobs_table.select().where(
                function_jobs_table.c.uuid == function_job_id
            )
        )
        row = await result.first()

        if row is None:
            msg = f"No function job found with id {function_job_id}."
            raise web.HTTPNotFound(reason=msg)

        return FunctionJobDB.model_validate(dict(row))


async def list_function_jobs(
    app: web.Application,
    connection: AsyncConnection | None = None,
) -> list[FunctionJobDB]:

    async with transaction_context(get_asyncpg_engine(app), connection) as conn:
        result = await conn.stream(function_jobs_table.select().where())
        rows = await result.all()
        if rows is None:
            return []

        return [FunctionJobDB.model_validate(dict(row)) for row in rows]


async def delete_function_job(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    function_job_id: FunctionID,
) -> None:
    async with transaction_context(get_asyncpg_engine(app), connection) as conn:
        await conn.execute(
            function_jobs_table.delete().where(
                function_jobs_table.c.uuid == function_job_id
            )
        )


async def find_cached_function_job(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    function_id: FunctionID,
    inputs: FunctionInputs,
) -> FunctionJobDB | None:

    async with transaction_context(get_asyncpg_engine(app), connection) as conn:
        result = await conn.stream(
            function_jobs_table.select().where(
                function_jobs_table.c.function_uuid == function_id,
                cast(function_jobs_table.c.inputs, Text) == json.dumps(inputs),
            ),
        )

        rows = await result.all()

        if rows is None:
            return None

        for row in rows:
            job = FunctionJobDB.model_validate(dict(row))
            if job.inputs == inputs:
                return job

        return None


async def list_function_job_collections(
    app: web.Application,
    connection: AsyncConnection | None = None,
) -> list[tuple[FunctionJobCollectionDB, list[FunctionJobID]]]:
    async with transaction_context(get_asyncpg_engine(app), connection) as conn:
        result = await conn.stream(function_job_collections_table.select().where())
        rows = await result.all()
        if rows is None:
            return []

        collections = []
        for row in rows:
            collection = FunctionJobCollection.model_validate(dict(row))
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
        return collections


async def get_function_job_collection(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    function_job_collection_id: FunctionID,
) -> tuple[FunctionJobCollectionDB, list[FunctionJobID]]:

    async with transaction_context(get_asyncpg_engine(app), connection) as conn:
        result = await conn.stream(
            function_job_collections_table.select().where(
                function_job_collections_table.c.uuid == function_job_collection_id
            )
        )
        row = await result.first()

        if row is None:
            msg = f"No function job collection found with id {function_job_collection_id}."
            raise web.HTTPNotFound(reason=msg)

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

        job_collection = FunctionJobCollectionDB.model_validate(dict(row))
        return job_collection, job_ids


async def register_function_job_collection(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    function_job_collection: FunctionJobCollection,
) -> tuple[FunctionJobCollectionDB, list[FunctionJobID]]:
    async with transaction_context(get_asyncpg_engine(app), connection) as conn:
        result = await conn.stream(
            function_job_collections_table.insert()
            .values(
                title=function_job_collection.title,
                description=function_job_collection.description,
            )
            .returning(*_FUNCTION_JOB_COLLECTIONS_TABLE_COLS)
        )
        row = await result.first()

        if row is None:
            msg = "No row was returned from the database after creating function job collection."
            raise ValueError(msg)

        for job_id in function_job_collection.job_ids:
            await conn.execute(
                function_job_collections_to_function_jobs_table.insert().values(
                    function_job_collection_uuid=row["uuid"],
                    function_job_uuid=job_id,
                )
            )

        job_collection = FunctionJobCollectionDB.model_validate(dict(row))
        return job_collection, function_job_collection.job_ids


async def delete_function_job_collection(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    function_job_collection_id: FunctionID,
) -> None:

    async with transaction_context(get_asyncpg_engine(app), connection) as conn:
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
