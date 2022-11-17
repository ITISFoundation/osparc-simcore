# pylint: disable=no-name-in-module
# pylint: disable=no-value-for-parameter
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument


import pytest
from aiopg.sa.engine import Engine
from simcore_postgres_database.utils_products import get_default_product_name


async def test_default_product(pg_engine: Engine, make_products_table):
    async with pg_engine.acquire() as conn:
        await make_products_table(conn)
        default_product = await get_default_product_name(conn)
        assert default_product == "s4l"


async def test_default_product_undefined(pg_engine: Engine, make_products_table):
    async with pg_engine.acquire() as conn:
        with pytest.raises(ValueError):
            await get_default_product_name(conn)
