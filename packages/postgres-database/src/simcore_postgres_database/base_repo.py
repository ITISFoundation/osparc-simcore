import logging
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

_logger = logging.getLogger(__name__)


@asynccontextmanager
async def get_or_create_connection(
    engine: AsyncEngine, connection: AsyncConnection | None = None
):
    # creator is responsible of closing connection
    is_connection_created = connection is None
    if is_connection_created:
        connection = await engine.connect()
    try:
        yield connection
    finally:
        if is_connection_created:
            await connection.close()


@asynccontextmanager
async def transaction_context(
    engine: AsyncEngine, connection: AsyncConnection | None = None
):
    async with get_or_create_connection(engine, connection) as conn:
        if conn.in_transaction():
            async with conn.begin_nested():  # savepoint
                yield conn
        else:
            try:
                async with conn.begin():
                    yield conn
            finally:
                assert not conn.closed  # nosec
                assert not conn.in_transaction()  # nosec
