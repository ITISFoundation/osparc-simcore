from typing import Literal
from uuid import UUID

from aiohttp import web
from models_library.functions import (
    FunctionAccessRightsDB,
    FunctionGroupAccessRights,
    FunctionID,
    FunctionJobCollectionID,
    FunctionJobID,
    FunctionsApiAccessRights,
    FunctionUserApiAccessRights,
)
from models_library.functions_errors import (
    FunctionExecuteAccessDeniedError,
    FunctionIDNotFoundError,
    FunctionJobCollectionExecuteAccessDeniedError,
    FunctionJobCollectionIDNotFoundError,
    FunctionJobCollectionReadAccessDeniedError,
    FunctionJobCollectionWriteAccessDeniedError,
    FunctionJobExecuteAccessDeniedError,
    FunctionJobIDNotFoundError,
    FunctionJobReadAccessDeniedError,
    FunctionJobWriteAccessDeniedError,
    FunctionReadAccessDeniedError,
    FunctionWriteAccessDeniedError,
)
from models_library.groups import GroupID
from models_library.products import ProductName
from models_library.users import UserID
from simcore_postgres_database.models.funcapi_api_access_rights_table import (
    funcapi_api_access_rights_table,
)
from simcore_postgres_database.models.funcapi_function_job_collections_access_rights_table import (
    function_job_collections_access_rights_table,
)
from simcore_postgres_database.models.funcapi_function_job_collections_table import (
    function_job_collections_table,
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
    pass_or_acquire_connection,
    transaction_context,
)
from sqlalchemy.ext.asyncio import AsyncConnection

from ..db.plugin import get_asyncpg_engine
from ..groups.api import list_all_user_groups_ids
from ._functions_exceptions import _ERRORS_MAP
from ._functions_table_cols import (
    _FUNCTION_JOB_COLLECTIONS_ACCESS_RIGHTS_TABLE_COLS,
    _FUNCTION_JOBS_ACCESS_RIGHTS_TABLE_COLS,
    _FUNCTIONS_ACCESS_RIGHTS_TABLE_COLS,
)


async def _internal_get_group_permissions(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    product_name: ProductName,
    object_type: Literal["function", "function_job", "function_job_collection"],
    object_ids: list[FunctionID | FunctionJobID | FunctionJobCollectionID],
) -> list[
    tuple[
        FunctionID | FunctionJobID | FunctionJobCollectionID,
        list[FunctionGroupAccessRights],
    ]
]:
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

    access_rights_list: list[tuple[UUID, list[FunctionGroupAccessRights]]] = []
    async with pass_or_acquire_connection(get_asyncpg_engine(app), connection) as conn:
        for object_id in object_ids:
            rows = [
                row
                async for row in await conn.stream(
                    access_rights_table.select().where(
                        getattr(access_rights_table.c, field_name) == object_id,
                        access_rights_table.c.product_name == product_name,
                    )
                )
            ]
            group_permissions = [
                FunctionGroupAccessRights(
                    group_id=row.group_id,
                    read=row.read,
                    write=row.write,
                    execute=row.execute,
                )
                for row in rows
            ]
            access_rights_list.append((object_id, group_permissions))

        return access_rights_list


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
        getattr(FunctionsApiAccessRights, f"{permission.upper()}_{object_type.upper()}S") for permission in permissions
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
                "read": FunctionReadAccessDeniedError(user_id=user_id, function_id=object_id),
                "write": FunctionWriteAccessDeniedError(user_id=user_id, function_id=object_id),
                "execute": FunctionExecuteAccessDeniedError(user_id=user_id, function_id=object_id),
            }
        case "function_job":
            errors = {
                "read": FunctionJobReadAccessDeniedError(user_id=user_id, function_job_id=object_id),
                "write": FunctionJobWriteAccessDeniedError(user_id=user_id, function_job_id=object_id),
                "execute": FunctionJobExecuteAccessDeniedError(user_id=user_id, function_job_id=object_id),
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


async def get_group_permissions(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    user_id: UserID,
    product_name: ProductName,
    object_type: Literal["function", "function_job", "function_job_collection"],
    object_ids: list[UUID],
) -> list[tuple[UUID, list[FunctionGroupAccessRights]]]:
    async with pass_or_acquire_connection(get_asyncpg_engine(app), connection) as conn:
        for object_id in object_ids:
            await check_user_permissions(
                app,
                connection=conn,
                user_id=user_id,
                product_name=product_name,
                object_id=object_id,
                object_type=object_type,
                permissions=["read"],
            )

        return await _internal_get_group_permissions(
            app,
            connection=connection,
            product_name=product_name,
            object_type=object_type,
            object_ids=object_ids,
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
) -> list[tuple[UUID, FunctionGroupAccessRights]]:
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

    access_rights_list: list[tuple[UUID, FunctionGroupAccessRights]] = []
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
                result = await transaction.execute(
                    access_rights_table.insert()
                    .values(
                        **{field_name: object_id},
                        group_id=permission_group_id,
                        product_name=product_name,
                        read=read if read is not None else False,
                        write=write if write is not None else False,
                        execute=execute if execute is not None else False,
                    )
                    .returning(
                        access_rights_table.c.group_id,
                        access_rights_table.c.read,
                        access_rights_table.c.write,
                        access_rights_table.c.execute,
                    )
                )
                row = result.one()
                access_rights_list.append((object_id, FunctionGroupAccessRights(**row)))
            else:
                # Update existing access rights only for non-None values
                update_values = {
                    "read": read if read is not None else row["read"],
                    "write": write if write is not None else row["write"],
                    "execute": execute if execute is not None else row["execute"],
                }

                update_result = await transaction.execute(
                    access_rights_table.update()
                    .where(
                        getattr(access_rights_table.c, field_name) == object_id,
                        access_rights_table.c.group_id == permission_group_id,
                    )
                    .values(**update_values)
                    .returning(
                        access_rights_table.c.group_id,
                        access_rights_table.c.read,
                        access_rights_table.c.write,
                        access_rights_table.c.execute,
                    )
                )
                updated_row = update_result.one()
                access_rights_list.append((object_id, FunctionGroupAccessRights(**updated_row)))

        return access_rights_list


async def set_group_permissions(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    user_id: UserID,
    permission_group_id: GroupID,
    product_name: ProductName,
    object_type: Literal["function", "function_job", "function_job_collection"],
    object_ids: list[FunctionID | FunctionJobID | FunctionJobCollectionID],
    read: bool | None = None,
    write: bool | None = None,
    execute: bool | None = None,
) -> list[tuple[FunctionID | FunctionJobID | FunctionJobCollectionID, FunctionGroupAccessRights]]:
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

        return await _internal_set_group_permissions(
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
            combined_permissions.read_function_job_collections |= row.read_function_job_collections
            combined_permissions.write_function_job_collections |= row.write_function_job_collections
            combined_permissions.execute_function_job_collections |= row.execute_function_job_collections

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
        FunctionIDNotFoundError | FunctionJobIDNotFoundError | FunctionJobCollectionIDNotFoundError
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
            error = FunctionJobCollectionIDNotFoundError(function_job_collection_id=object_id)

    async with pass_or_acquire_connection(get_asyncpg_engine(app), connection) as conn:
        result = await conn.execute(main_table.select().where(main_table.c.uuid == object_id))
        row = result.one_or_none()

        if row is None:
            raise error
        return True


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
        combined_permissions = FunctionAccessRightsDB(read=False, write=False, execute=False)

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
