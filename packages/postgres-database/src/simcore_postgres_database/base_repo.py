from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine


@asynccontextmanager
async def get_or_create_connection(
    engine: AsyncEngine, connection: AsyncConnection | None = None
):
    close_conn = False
    if connection is None:
        connection = await engine.connect()
        close_conn = True
    try:
        yield connection
    finally:
        if close_conn:
            await connection.close()


@asynccontextmanager
async def transaction_context(
    engine: AsyncEngine, connection: AsyncConnection | None = None
):
    async with get_or_create_connection(engine, connection) as conn:
        if conn.in_transaction():
            async with conn.begin_nested():
                yield conn
        else:
            async with conn.begin():
                yield conn
