# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


from collections.abc import AsyncIterator

import pytest
import sqlalchemy as sa
import sqlalchemy.exc
from faker import Faker
from pytest_simcore.helpers.faker_factories import random_product
from simcore_postgres_database.models.products import products
from simcore_postgres_database.models.products_prices import products_prices
from simcore_postgres_database.utils_products_prices import (
    get_product_latest_price_info_or_none,
    get_product_latest_stripe_info,
    is_payment_enabled,
)
from sqlalchemy.engine.row import Row
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine


@pytest.fixture
async def connection(asyncpg_engine: AsyncEngine) -> AsyncIterator[AsyncConnection]:
    async with asyncpg_engine.connect() as conn:
        isolation_level = await conn.get_isolation_level()
        assert isolation_level == "READ COMMITTED"
        yield conn


@pytest.fixture
async def fake_product(connection: AsyncConnection) -> Row:
    result = await connection.execute(
        products.insert()
        .values(random_product(name="tip", group_id=None))
        .returning(sa.literal_column("*")),
    )
    await connection.commit()

    async with connection.begin():
        result = await connection.execute(
            products.insert()
            .values(random_product(name="s4l", group_id=None))
            .returning(sa.literal_column("*")),
        )

    return result.one()


async def test_creating_product_prices(
    asyncpg_engine: AsyncEngine,
    connection: AsyncConnection,
    fake_product: Row,
    faker: Faker,
):
    # a price per product
    async with connection.begin():
        result = await connection.execute(
            products_prices.insert()
            .values(
                product_name=fake_product.name,
                usd_per_credit=100,
                comment="PO Mr X",
                stripe_price_id=faker.word(),
                stripe_tax_rate_id=faker.word(),
            )
            .returning(sa.literal_column("*")),
        )
        got = result.one()
        assert got

        # insert still NOT commited but can read from this connection
        read_query = sa.select(products_prices).where(
            products_prices.c.product_name == fake_product.name
        )
        result = await connection.execute(read_query)
        assert result.one()._asdict() == got._asdict()

        assert connection.in_transaction() is True

        # cannot read from other connection though
        async with asyncpg_engine.connect() as other_connection:
            result = await other_connection.execute(read_query)
            assert result.one_or_none() is None

    # AFTER commit
    assert connection.in_transaction() is False
    async with asyncpg_engine.connect() as yet_another_connection:
        result = await yet_another_connection.execute(read_query)
        assert result.one()._asdict() == got._asdict()


async def test_non_negative_price_not_allowed(
    connection: AsyncConnection, fake_product: Row, faker: Faker
):

    assert not connection.in_transaction()

    # WRITE: negative price not allowed
    with pytest.raises(sqlalchemy.exc.IntegrityError) as exc_info:
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
    assert connection.in_transaction()
    await connection.rollback()
    assert not connection.in_transaction()

    # WRITE: zero price is allowed
    result = await connection.execute(
        products_prices.insert()
        .values(
            product_name=fake_product.name,
            usd_per_credit=0,  # <----- ZERO
            comment="PO Mr X",
            stripe_price_id=faker.word(),
            stripe_tax_rate_id=faker.word(),
        )
        .returning("*")
    )

    assert result.one()

    assert connection.in_transaction()
    await connection.commit()
    assert not connection.in_transaction()

    with pytest.raises(sqlalchemy.exc.ResourceClosedError):
        # can only get result once!
        assert result.one()

    # READ
    result = await connection.execute(sa.select(products_prices))
    assert connection.in_transaction()

    assert result.one()
    with pytest.raises(sqlalchemy.exc.ResourceClosedError):
        # can only get result once!
        assert result.one()


async def test_delete_price_constraints(
    connection: AsyncConnection, fake_product: Row, faker: Faker
):
    # products_prices
    async with connection.begin():
        await connection.execute(
            products_prices.insert().values(
                product_name=fake_product.name,
                usd_per_credit=10,
                comment="PO Mr X",
                stripe_price_id=faker.word(),
                stripe_tax_rate_id=faker.word(),
            )
        )

    # BAD DELETE:
    # should not be able to delete a product w/o deleting price first
    async with connection.begin():
        with pytest.raises(sqlalchemy.exc.IntegrityError, match="delete") as exc_info:
            await connection.execute(products.delete())

        # NOTE: that asyncpg.exceptions are converted to sqlalchemy.exc
        # sqlalchemy.exc.IntegrityError: (sqlalchemy.dialects.postgresql.asyncpg.IntegrityError) <class 'asyncpg.exceptions.ForeignKeyViolationError'>:
        assert "asyncpg.exceptions.ForeignKeyViolationError" in exc_info.value.args[0]

    # GOOD DELETE: this is the correct way to delete
    async with connection.begin():
        await connection.execute(products_prices.delete())
        await connection.execute(products.delete())


async def test_get_product_latest_price_or_none(
    connection: AsyncConnection, fake_product: Row, faker: Faker
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
    connection: AsyncConnection, fake_product: Row, faker: Faker
):
    # initial price
    async with connection.begin():
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
    async with connection.begin():
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
    connection: AsyncConnection, fake_product: Row, faker: Faker
):
    stripe_price_id_value = faker.word()
    stripe_tax_rate_id_value = faker.word()

    # products_prices
    async with connection.begin():
        await connection.execute(
            products_prices.insert().values(
                product_name=fake_product.name,
                usd_per_credit=10,
                comment="PO Mr X",
                stripe_price_id=stripe_price_id_value,
                stripe_tax_rate_id=stripe_tax_rate_id_value,
            )
        )

    # undefined product
    with pytest.raises(ValueError, match="undefined"):
        await get_product_latest_stripe_info(connection, product_name="undefined")

    # defined product
    product_stripe_info = await get_product_latest_stripe_info(
        connection, product_name=fake_product.name
    )
    assert product_stripe_info[0] == stripe_price_id_value
    assert product_stripe_info[1] == stripe_tax_rate_id_value
