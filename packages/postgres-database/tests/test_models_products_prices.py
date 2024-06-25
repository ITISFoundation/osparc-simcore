# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


import pytest
import sqlalchemy as sa
from aiopg.sa.connection import SAConnection
from aiopg.sa.result import RowProxy
from faker import Faker
from pytest_simcore.helpers.faker_factories import random_product
from simcore_postgres_database.errors import CheckViolation, ForeignKeyViolation
from simcore_postgres_database.models.products import products
from simcore_postgres_database.models.products_prices import products_prices
from simcore_postgres_database.utils_products_prices import (
    get_product_latest_price_info_or_none,
    get_product_latest_stripe_info,
    is_payment_enabled,
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
    connection: SAConnection, fake_product: RowProxy, faker: Faker
):
    # a price per product
    result = await connection.execute(
        products_prices.insert()
        .values(
            product_name=fake_product.name,
            usd_per_credit=100,
            comment="PO Mr X",
            stripe_price_id=faker.word(),
            stripe_tax_rate_id=faker.word(),
        )
        .returning(sa.literal_column("*"))
    )
    product_prices = await result.first()
    assert product_prices


async def test_non_negative_price_not_allowed(
    connection: SAConnection, fake_product: RowProxy, faker: Faker
):
    # negative price not allowed
    with pytest.raises(CheckViolation) as exc_info:
        await connection.execute(
            products_prices.insert().values(
                product_name=fake_product.name,
                usd_per_credit=-100,  # <----- NEGATIVE
                comment="PO Mr X",
                stripe_price_id=faker.word(),
                stripe_tax_rate_id=faker.word(),
            )
        )

    assert exc_info.value

    # zero price is allowed
    await connection.execute(
        products_prices.insert().values(
            product_name=fake_product.name,
            usd_per_credit=0,  # <----- ZERO
            comment="PO Mr X",
            stripe_price_id=faker.word(),
            stripe_tax_rate_id=faker.word(),
        )
    )


async def test_delete_price_constraints(
    connection: SAConnection, fake_product: RowProxy, faker: Faker
):
    # products_prices
    await connection.execute(
        products_prices.insert().values(
            product_name=fake_product.name,
            usd_per_credit=10,
            comment="PO Mr X",
            stripe_price_id=faker.word(),
            stripe_tax_rate_id=faker.word(),
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
    connection: SAConnection, fake_product: RowProxy, faker: Faker
):
    # undefined product
    assert (
        await get_product_latest_price_info_or_none(
            connection, product_name="undefined"
        )
        is None
    )

    assert await is_payment_enabled(connection, product_name="undefined") is False

    # defined product but undefined price
    assert (
        await get_product_latest_price_info_or_none(
            connection, product_name=fake_product.name
        )
        is None
    )

    assert await is_payment_enabled(connection, product_name=fake_product.name) is False


async def test_price_history_of_a_product(
    connection: SAConnection, fake_product: RowProxy, faker: Faker
):
    # initial price
    await connection.execute(
        products_prices.insert().values(
            product_name=fake_product.name,
            usd_per_credit=1,
            comment="PO Mr X",
            stripe_price_id=faker.word(),
            stripe_tax_rate_id=faker.word(),
        )
    )

    # new price
    await connection.execute(
        products_prices.insert().values(
            product_name=fake_product.name,
            usd_per_credit=2,
            comment="Update by Mr X",
            stripe_price_id=faker.word(),
            stripe_tax_rate_id=faker.word(),
        )
    )

    # latest is 2 USD!
    assert await get_product_latest_price_info_or_none(
        connection, product_name=fake_product.name
    ) == (2, 10)

    assert await is_payment_enabled(connection, product_name=fake_product.name) is True


async def test_get_product_latest_stripe_info(
    connection: SAConnection, fake_product: RowProxy, faker: Faker
):
    stripe_price_id_value = faker.word()
    stripe_tax_rate_id_value = faker.word()

    # products_prices
    await connection.execute(
        products_prices.insert().values(
            product_name=fake_product.name,
            usd_per_credit=10,
            comment="PO Mr X",
            stripe_price_id=stripe_price_id_value,
            stripe_tax_rate_id=stripe_tax_rate_id_value,
        )
    )

    # defined product
    product_stripe_info = await get_product_latest_stripe_info(
        connection, product_name=fake_product.name
    )
    assert product_stripe_info[0] == stripe_price_id_value
    assert product_stripe_info[1] == stripe_tax_rate_id_value

    # undefined product
    with pytest.raises(ValueError) as exc_info:
        await get_product_latest_stripe_info(connection, product_name="undefined")
