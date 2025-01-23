import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import TypeVar

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

_logger = logging.getLogger(__name__)


@asynccontextmanager
async def pass_or_acquire_connection(
    engine: AsyncEngine, connection: AsyncConnection | None = None
) -> AsyncIterator[AsyncConnection]:
    """
    When to use: For READ operations!
    It ensures that a connection is available for use within the context,
    either by using an existing connection passed as a parameter or by acquiring a new one from the engine.

    The caller must manage the lifecycle of any connection explicitly passed in, but the function handles the
    cleanup for connections it creates itself.

    This function **does not open new transactions** and therefore is recommended only for read-only database operations.
    """
    # NOTE: When connection is passed, the engine is actually not needed
    # NOTE: Creator is responsible of closing connection
    is_connection_created = connection is None
    if is_connection_created:
        connection = await engine.connect()
    try:
        assert connection  # nosec
        yield connection
    finally:
        assert connection  # nosec
        assert not connection.closed  # nosec
        if is_connection_created and connection:
            await connection.close()


@asynccontextmanager
async def transaction_context(
    engine: AsyncEngine, connection: AsyncConnection | None = None
):
    """
    When to use: For WRITE operations!
    This function manages the database connection and ensures that a transaction context is established for write operations.
    It supports both outer and nested transactions, providing flexibility for scenarios where transactions may already exist in the calling context.
    """
    async with pass_or_acquire_connection(engine, connection) as conn:
        if conn.in_transaction():
            async with conn.begin_nested():  # inner transaction (savepoint)
                yield conn
        else:
            try:
                async with conn.begin():  # outer transaction (savepoint)
                    yield conn
            finally:
                assert not conn.closed  # nosec
                assert not conn.in_transaction()  # nosec


SQLModel = TypeVar(
    # Towards using https://sqlmodel.tiangolo.com/#create-a-sqlmodel-model
    "SQLModel",
    bound="BaseModel",
)


def get_columns_from_db_model(
    table: sa.Table, model_cls: type[SQLModel]
) -> list[sa.Column]:
    """
    Usage example:

        query = sa.select( get_columns_from_db_model(project, ProjectDB) )

        or

        query = (
                 project.insert().
                 # ...
                 .returning(*get_columns_from_db_model(project, ProjectDB))
                )
    """
    return [table.columns[field_name] for field_name in model_cls.model_fields]
