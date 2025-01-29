# pylint: disable=no-name-in-module
# pylint: disable=no-value-for-parameter
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument


from collections.abc import Callable

import sqlalchemy as sa
from aiopg.sa.engine import Engine
from aiopg.sa.result import ResultProxy, RowProxy
from simcore_postgres_database.webserver_models import products


async def test_load_products(
    aiopg_engine: Engine, make_products_table: Callable, products_regex: dict
):
    exclude = {
        products.c.created,
        products.c.modified,
    }

    async with aiopg_engine.acquire() as conn:
        await make_products_table(conn)

        stmt = sa.select(*[c for c in products.columns if c not in exclude])
        result: ResultProxy = await conn.execute(stmt)
        assert result.returns_rows

        rows: list[RowProxy] = await result.fetchall()
        assert rows

        assert {
            row[products.c.name]: row[products.c.host_regex] for row in rows
        } == products_regex
