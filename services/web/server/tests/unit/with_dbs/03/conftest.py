# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


from collections.abc import AsyncIterable, AsyncIterator
from decimal import Decimal

import aiopg.sa
import pytest
import sqlalchemy as sa
from aiopg.sa import create_engine
from aiopg.sa.connection import SAConnection
from faker import Faker
from models_library.products import ProductName
from pytest_simcore.helpers.rawdata_fakers import random_product
from simcore_postgres_database.models.products import products
from simcore_postgres_database.models.products_prices import products_prices
from simcore_postgres_database.models.user_preferences import user_preferences_frontend
from simcore_postgres_database.utils_products import get_or_create_product_group
from simcore_service_webserver.statics._constants import (
    FRONTEND_APP_DEFAULT,
    FRONTEND_APPS_AVAILABLE,
)


@pytest.fixture
async def drop_all_preferences(
    aiopg_engine: aiopg.sa.engine.Engine,
) -> AsyncIterator[None]:
    yield
    async with aiopg_engine.acquire() as conn:
        await conn.execute(user_preferences_frontend.delete())


@pytest.fixture
async def _pre_connection(postgres_db: sa.engine.Engine) -> AsyncIterable[SAConnection]:
    # NOTE: call to postgres BEFORE app starts
    async with await create_engine(
        f"{postgres_db.url}"
    ) as engine, engine.acquire() as conn:
        yield conn


@pytest.fixture
async def all_products_names(
    _pre_connection: SAConnection,
) -> AsyncIterable[list[ProductName]]:
    # default product
    result = await _pre_connection.execute(
        products.select().order_by(products.c.priority)
    )
    rows = await result.fetchall()
    assert rows
    assert len(rows) == 1
    osparc_product_row = rows[0]
    assert osparc_product_row.name == FRONTEND_APP_DEFAULT
    assert osparc_product_row.priority == 0

    # creates remaing products for front-end
    priority = 1
    for name in FRONTEND_APPS_AVAILABLE:
        if name != FRONTEND_APP_DEFAULT:
            result = await _pre_connection.execute(
                products.insert().values(
                    random_product(
                        name=name,
                        priority=priority,
                        login_settings=osparc_product_row.login_settings,
                        group_id=None,
                    )
                )
            )
            await get_or_create_product_group(_pre_connection, product_name=name)
            priority += 1

    # get all products
    result = await _pre_connection.execute(
        sa.select(products.c.name).order_by(products.c.priority)
    )
    rows = await result.fetchall()

    yield [r.name for r in rows]

    await _pre_connection.execute(products_prices.delete())
    await _pre_connection.execute(
        products.delete().where(products.c.name != FRONTEND_APP_DEFAULT)
    )


@pytest.fixture
async def all_product_prices(
    _pre_connection: SAConnection,
    all_products_names: list[ProductName],
    faker: Faker,
) -> dict[ProductName, Decimal | None]:
    """Initial list of prices for all products"""

    # initial list of prices
    product_price = {
        "osparc": Decimal(0),  # free of charge
        "tis": Decimal(5),
        "s4l": Decimal(9),
        "s4llite": Decimal(0),  # free of charge
        "s4lacad": Decimal(1.1),
    }

    result = {}
    for product_name in all_products_names:
        usd_or_none = product_price.get(product_name, None)
        if usd_or_none is not None:
            await _pre_connection.execute(
                products_prices.insert().values(
                    product_name=product_name,
                    usd_per_credit=usd_or_none,
                    comment=faker.sentence(),
                )
            )

        result[product_name] = usd_or_none

    return result


@pytest.fixture
async def latest_osparc_price(
    all_product_prices: dict[ProductName, Decimal],
    _pre_connection: SAConnection,
) -> Decimal:
    """This inserts a new price for osparc in the history
    (i.e. the old price of osparc is still in the database)
    """

    usd = await _pre_connection.scalar(
        products_prices.insert()
        .values(
            product_name="osparc",
            usd_per_credit=all_product_prices["osparc"] + 5,
            comment="New price for osparc",
        )
        .returning(products_prices.c.usd_per_credit)
    )
    assert usd is not None
    assert usd != all_product_prices["osparc"]
    return Decimal(usd)
