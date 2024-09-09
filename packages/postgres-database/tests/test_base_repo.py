# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


from typing import Any, TypedDict

import pytest
import sqlalchemy as sa
from simcore_postgres_database.base_repo import (
    get_or_create_connection,
    transaction_context,
)
from simcore_postgres_database.models.tags import tags
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine


class _PageDict(TypedDict):
    total_count: int
    rows: list[dict[str, Any]]


class OneResourceRepoDemo:
    # This is a PROTOTYPE of how one could implement a generic
    # repo that provides CRUD operations providing a given table
    def __init__(self, engine: AsyncEngine, table: sa.Table):
        if "id" not in table.columns:
            msg = "id column expected"
            raise ValueError(msg)
        self.table = table

        self.engine = engine

    async def create(self, connection: AsyncConnection | None = None, **kwargs) -> int:
        async with transaction_context(self.engine, connection) as conn:
            result = await conn.execute(self.table.insert().values(**kwargs))
            assert result  # nosec
            return result.inserted_primary_key[0]

    async def get_by_id(
        self,
        connection: AsyncConnection | None = None,
        *,
        record_id: int,
    ) -> dict[str, Any] | None:
        async with get_or_create_connection(self.engine, connection) as conn:
            result = await conn.execute(
                sa.select(self.table).where(self.table.c.id == record_id)
            )
            record = result.fetchone()
            return dict(record) if record else None

    async def get_page(
        self,
        connection: AsyncConnection | None = None,
        *,
        limit: int,
        offset: int,
    ) -> _PageDict:
        async with get_or_create_connection(self.engine, connection) as conn:
            # Compute total count
            total_count_query = sa.select(sa.func.count()).select_from(self.table)
            total_count_result = await conn.execute(total_count_query)
            total_count = total_count_result.scalar()

            # Fetch paginated results
            query = sa.select(self.table).limit(limit).offset(offset)
            result = await conn.execute(query)
            records = [dict(**row) for row in result.fetchall()]

            return _PageDict(total_count=total_count or 0, rows=records)

    async def update(
        self,
        connection: AsyncConnection | None = None,
        *,
        record_id: int,
        **values,
    ) -> bool:
        async with transaction_context(self.engine, connection) as conn:
            result = await conn.execute(
                self.table.update().where(self.table.c.id == record_id).values(**values)
            )
            return result.rowcount > 0

    async def delete(
        self,
        connection: AsyncConnection | None = None,
        *,
        record_id: int,
    ) -> bool:
        async with transaction_context(self.engine, connection) as conn:
            result = await conn.execute(
                self.table.delete().where(self.table.c.id == record_id)
            )
            return result.rowcount > 0


# async def test_it(asyncpg_engine: AsyncEngine):

#     async with asyncpg_engine.connect() as conn:
#         async with conn.begin():
#             conn.execute()


async def test_transaction_context(asyncpg_engine: AsyncEngine):
    #
    # Similar to example in https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html#synopsis-core
    # using tags

    tags_repo = OneResourceRepoDemo(engine=asyncpg_engine, table=tags)

    # (1) Using transaction_context and fails
    fake_error_msg = "some error"

    def _something_raises_here():
        raise RuntimeError(fake_error_msg)

    async def _create_blue_like_tags(connection):
        # NOTE: embedded transaction here!!!
        async with transaction_context(asyncpg_engine, connection) as conn:
            await tags_repo.create(conn, name="cyan tag", color="cyan")
            _something_raises_here()
            await tags_repo.create(conn, name="violet tag", color="violet")

    async def _create_four_tags(connection):
        await tags_repo.create(connection, name="red tag", color="red")
        await _create_blue_like_tags(connection)
        await tags_repo.create(connection, name="green tag", color="green")

    with pytest.raises(RuntimeError, match=fake_error_msg):
        async with transaction_context(asyncpg_engine) as conn:
            await tags_repo.create(conn, name="red tag", color="red")
            _something_raises_here()
            await tags_repo.create(conn, name="green tag", color="green")

    print(asyncpg_engine.pool.status())
    assert conn.closed

    page = await tags_repo.get_page(limit=50, offset=0)
    assert page["total_count"] == 0, "Transaction did not happen"

    # (2) using internal connections
    await tags_repo.create(name="blue tag", color="blue")
    await tags_repo.create(name="red tag", color="red")
    page = await tags_repo.get_page(limit=50, offset=0)
    assert page["total_count"] == 2

    # (3) using external embedded
    async with transaction_context(asyncpg_engine) as conn:
        page = await tags_repo.get_page(conn, limit=50, offset=0)
        assert page["total_count"] == 2

        # select a Result, which will be delivered with buffered results
        result = await conn.execute(sa.select(tags).where(tags.c.name == "blue tag"))
        assert result.fetchall()
