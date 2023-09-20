# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


import pytest
import sqlalchemy as sa
from aiopg.sa.connection import SAConnection
from aiopg.sa.result import RowProxy
from pytest_simcore.helpers.rawdata_fakers import random_product
from simcore_postgres_database.errors import CheckViolation, ForeignKeyViolation
from simcore_postgres_database.models.products import products
from simcore_postgres_database.models.products_prices import products_prices
from simcore_postgres_database.utils_products_prices import (
    get_product_latest_credit_price_or_none,
)


@pytest.fixture
async def fake_product(connection: SAConnection) -> RowProxy:
    result = await connection.execute(
        products.insert()
        .values(random_product(group_id=None))
        .returning(sa.literal_column("*"))
    )
    product = await result.first()
    assert product is not None
    return product


async def test_creating_product_prices(
    connection: SAConnection, fake_product: RowProxy
):
    # a price per product
    result = await connection.execute(
        products_prices.insert()
        .values(
            product_name=fake_product.name,
            usd_per_credit=100,
            comment="PO Mr X",
        )
        .returning(sa.literal_column("*"))
    )
    product_prices = await result.first()
    assert product_prices


async def test_non_negative_price_not_allowed(
    connection: SAConnection, fake_product: RowProxy
):
    # negative price not allowed
    with pytest.raises(CheckViolation) as exc_info:
        await connection.execute(
            products_prices.insert().values(
                product_name=fake_product.name,
                usd_per_credit=-100,  # <----- NEGATIVE
                comment="PO Mr X",
            )
        )

    assert exc_info.value

    # zero price is allowed
    await connection.execute(
        products_prices.insert().values(
            product_name=fake_product.name,
            usd_per_credit=0,  # <----- ZERO
            comment="PO Mr X",
        )
    )


async def test_delete_price_constraints(
    connection: SAConnection, fake_product: RowProxy
):
    # products_prices
    await connection.execute(
        products_prices.insert().values(
            product_name=fake_product.name,
            usd_per_credit=10,
            comment="PO Mr X",
        )
    )

    # should not be able to delete a product w/o deleting price first
    with pytest.raises(ForeignKeyViolation) as exc_info:
        await connection.execute(products.delete())

    assert exc_info.match("delete")

    # this is the correct way to delete
    await connection.execute(products_prices.delete())
    await connection.execute(products.delete())


async def test_get_product_latest_price_or_none(
    connection: SAConnection, fake_product: RowProxy
):
    # undefined product
    assert (
        await get_product_latest_credit_price_or_none(
            connection, product_name="undefined"
        )
        is None
    )

    # defined product but undefined price
    assert (
        await get_product_latest_credit_price_or_none(
            connection, product_name=fake_product.name
        )
        is None
    )


async def test_price_history_of_a_product(
    connection: SAConnection, fake_product: RowProxy
):
    # initial price
    await connection.execute(
        products_prices.insert().values(
            product_name=fake_product.name,
            usd_per_credit=1,
            comment="PO Mr X",
        )
    )

    # new price
    await connection.execute(
        products_prices.insert().values(
            product_name=fake_product.name,
            usd_per_credit=2,
            comment="Update by Mr X",
        )
    )

    # latest is 2 USD!
    assert (
        await get_product_latest_credit_price_or_none(
            connection, product_name=fake_product.name
        )
        == 2
    )
