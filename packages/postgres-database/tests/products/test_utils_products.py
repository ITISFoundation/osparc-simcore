# pylint: disable=no-name-in-module
# pylint: disable=no-value-for-parameter
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

from collections.abc import Callable

import pytest
import sqlalchemy as sa
from simcore_postgres_database.models.groups import GroupType, groups
from simcore_postgres_database.models.products import products
from simcore_postgres_database.utils_products import (
    get_default_product_name,
    get_or_create_product_group,
    get_product_group_id,
)
from sqlalchemy.ext.asyncio import AsyncEngine


async def test_default_product(
    asyncpg_engine: AsyncEngine, make_products_table: Callable
):
    async with asyncpg_engine.begin() as conn:
        await make_products_table(conn)
        default_product = await get_default_product_name(conn)
        assert default_product == "s4l"


@pytest.mark.parametrize("pg_sa_engine", ["sqlModels"], indirect=True)
async def test_default_product_undefined(asyncpg_engine: AsyncEngine):
    async with asyncpg_engine.connect() as conn:
        with pytest.raises(ValueError, match="No product"):
            await get_default_product_name(conn)


async def test_get_or_create_group_product(
    asyncpg_engine: AsyncEngine, make_products_table: Callable
):
    async with asyncpg_engine.connect() as conn:
        await make_products_table(conn)

        async for product_row in await conn.stream(
            sa.select(products.c.name, products.c.group_id).order_by(
                products.c.priority
            )
        ):
            # get or create
            product_group_id = await get_or_create_product_group(
                conn, product_name=product_row.name
            )

            # check product's group
            if product_row.group_id is not None:
                # if existed, gets the same
                assert product_group_id == product_row.group_id

            result = await conn.execute(
                groups.select().where(groups.c.gid == product_group_id)
            )
            product_group = result.one()

            # check product's group
            assert product_group.type == GroupType.STANDARD
            assert product_group.name == product_row.name
            assert product_group.description == f"{product_row.name} product group"

            # idempotent
            for _ in range(3):
                assert (
                    await get_or_create_product_group(
                        conn, product_name=product_row.name
                    )
                    == product_group_id
                )

            # does not create more groups with this name
            result = await conn.execute(
                groups.select().where(groups.c.name == product_row.name)
            )
            assert result.one()

            assert product_group_id == await get_product_group_id(
                conn, product_name=product_row.name
            )

            # group-id is UPDATED -> product.group_id is updated to the new value
            await conn.execute(
                groups.update().where(groups.c.gid == product_group_id).values(gid=1000)
            )
            product_group_id = await get_product_group_id(
                conn, product_name=product_row.name
            )
            assert product_group_id == 1000

            # if group is DELETED -> product.group_id=null
            await conn.execute(groups.delete().where(groups.c.gid == product_group_id))
            product_group_id = await get_product_group_id(
                conn, product_name=product_row.name
            )
            assert product_group_id is None
