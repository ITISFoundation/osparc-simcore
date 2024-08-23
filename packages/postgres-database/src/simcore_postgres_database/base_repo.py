from contextlib import asynccontextmanager
from typing import Any, TypedDict

import sqlalchemy as sa
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


class _PageDict(TypedDict):
    total_count: int
    rows: list[dict[str, Any]]


class MinimalRepo:
    def __init__(self, engine: AsyncEngine, table: sa.Table):
        self.engine = engine
        self.table = table

    async def create(self, connection: AsyncConnection | None = None, **kwargs) -> int:
        async with get_or_create_connection(self.engine, connection) as conn:
            result = await conn.execute(self.table.insert().values(**kwargs))
            await conn.commit()
            assert result  # nosec
            return result.inserted_primary_key[0]

    async def get_by_id(
        self, record_id: int, connection: AsyncConnection | None = None
    ) -> dict[str, Any] | None:
        async with get_or_create_connection(self.engine, connection) as conn:
            result = await conn.execute(
                sa.select(self.table).where(self.table.c.id == record_id)
            )
            record = result.fetchone()
            return dict(record) if record else None

    async def get_page(
        self, limit: int, offset: int, connection: AsyncConnection | None = None
    ) -> _PageDict:
        async with get_or_create_connection(self.engine, connection) as conn:
            # Compute total count
            total_count_query = sa.select(sa.func.count()).select_from(self.table)
            total_count_result = await conn.execute(total_count_query)
            total_count = total_count_result.scalar()

            # Fetch paginated results
            query = sa.select(self.table).limit(limit).offset(offset)
            result = await conn.execute(query)
            records = [dict(row) for row in result.fetchall()]

            return _PageDict(total_count=total_count or 0, rows=records)

    async def update(
        self, record_id: int, connection: AsyncConnection | None = None, **values
    ) -> bool:
        async with get_or_create_connection(self.engine, connection) as conn:
            result = await conn.execute(
                self.table.update().where(self.table.c.id == record_id).values(**values)
            )
            await conn.commit()
            return result.rowcount > 0

    async def delete(
        self, record_id: int, connection: AsyncConnection | None = None
    ) -> bool:
        async with get_or_create_connection(self.engine, connection) as conn:
            result = await conn.execute(
                self.table.delete().where(self.table.c.id == record_id)
            )
            await conn.commit()
            return result.rowcount > 0
