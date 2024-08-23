# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

from collections.abc import AsyncIterator, Callable

import sqlalchemy as sa
from simcore_postgres_database.base_repo import MinimalRepo, transaction_context
from sqlalchemy.ext.asyncio import AsyncEngine


async def asyncio_engine(
    make_asyncio_engine: Callable[[bool], AsyncEngine]
) -> AsyncIterator[AsyncEngine]:
    engine = make_asyncio_engine(echo=True)
    try:
        yield engine
    except Exception:
        # for AsyncEngine created in function scope, close and
        # clean-up pooled connections
        await engine.dispose()


async def test_it(asyncio_engine: AsyncEngine):

    meta = sa.MetaData()
    t1 = sa.Table("t1", meta, sa.Column("name", sa.String(50), primary_key=True))

    t1_repo = MinimalRepo(engine=asyncio_engine, table=t1)

    async with transaction_context(asyncio_engine) as conn:
        await conn.run_sync(meta.drop_all)
        await conn.run_sync(meta.create_all)

        await t1_repo.create(conn, name="some name 1")
        await t1_repo.create(conn, name="some name 2")

    async with transaction_context(asyncio_engine) as conn:

        page = await t1_repo.get_page(limit=50, offset=0, connection=conn)

        assert page["total_count"] == 2

        # select a Result, which will be delivered with buffered
        # results
        result = await conn.execute(sa.select(t1).where(t1.c.name == "some name 1"))
        print(result.fetchall())
