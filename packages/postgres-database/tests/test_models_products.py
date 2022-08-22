# pylint: disable=no-name-in-module
# pylint: disable=no-value-for-parameter
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument


from typing import Callable

import pytest
import sqlalchemy as sa
from aiopg.sa.engine import Engine
from aiopg.sa.exc import ResourceClosedError
from aiopg.sa.result import ResultProxy, RowProxy
from simcore_postgres_database.webserver_models import products


@pytest.fixture
def product_sample() -> dict:
    return {
        "osparc": r"^osparc.",
        "s4l": r"(^s4l[\.-])|(^sim4life\.)",
        "tis": r"(^ti.[\.-])|(^ti-solution\.)",
    }


@pytest.fixture
def make_products_table(
    product_sample: dict,
) -> Callable:
    async def _make(conn) -> None:
        for name, regex in product_sample.items():
            result = await conn.execute(
                products.insert().values(name=name, host_regex=regex)
            )

            assert result.closed
            assert not result.returns_rows
            with pytest.raises(ResourceClosedError):
                await result.scalar()

    return _make


async def test_load_products(
    pg_engine: Engine, make_products_table: Callable, product_sample: dict
):
    exclude = {
        products.c.created,
        products.c.modified,
    }

    async with pg_engine.acquire() as conn:
        await make_products_table(conn)

        stmt = sa.select([c for c in products.columns if c not in exclude])
        result: ResultProxy = await conn.execute(stmt)
        assert result.returns_rows

        rows: list[RowProxy] = await result.fetchall()
        assert rows

        assert {
            row[products.c.name]: row[products.c.host_regex] for row in rows
        } == product_sample
