import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

_logger = logging.getLogger(__name__)


@asynccontextmanager
async def pass_or_acquire_connection(
    engine: AsyncEngine, connection: AsyncConnection | None = None
) -> AsyncIterator[AsyncConnection]:
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
