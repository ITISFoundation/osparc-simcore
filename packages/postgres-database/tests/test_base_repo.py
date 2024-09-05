# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


from typing import Any, TypedDict

import sqlalchemy as sa
from simcore_postgres_database.base_repo import (
    get_or_create_connection,
    transaction_context,
)
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine


class _PageDict(TypedDict):
    total_count: int
    rows: list[dict[str, Any]]


class OneResourceRepoDemo:
    # This is a PROTOTYPE of how one could implement a generic
    # repo that provides CRUD operations providing a given table
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


async def test_sqlachemy_asyncio_example(asyncpg_engine: AsyncEngine):
    #
    # Same example as in https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html#synopsis-core
    # but using `t1_repo`
    #
    meta = sa.MetaData()
    t1 = sa.Table("t1", meta, sa.Column("name", sa.String(50), primary_key=True))

    t1_repo = OneResourceRepoDemo(engine=asyncpg_engine, table=t1)

    async with transaction_context(asyncpg_engine) as conn:

        await conn.run_sync(meta.drop_all)
        await conn.run_sync(meta.create_all)

        await t1_repo.create(conn, name="some name 1")
        await t1_repo.create(conn, name="some name 2")

    async with transaction_context(asyncpg_engine) as conn:
        page = await t1_repo.get_page(limit=50, offset=0, connection=conn)

        assert page["total_count"] == 2

        # select a Result, which will be delivered with buffered results
        result = await conn.execute(sa.select(t1).where(t1.c.name == "some name 1"))
        assert result.fetchall()
