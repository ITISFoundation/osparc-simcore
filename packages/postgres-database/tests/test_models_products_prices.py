# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


import sqlalchemy as sa
from aiopg.sa.connection import SAConnection
from pytest_simcore.helpers.rawdata_fakers import random_product, random_user
from simcore_postgres_database.models.products import products
from simcore_postgres_database.models.products_prices import products_prices
from simcore_postgres_database.models.users import users


async def test_creating_product_prices(connection: SAConnection):
    # a user
    result = await connection.execute(
        users.insert()
        .values(random_user(primary_gid=1))
        .returning(sa.literal_column("*"))
    )
    user = await result.first()
    assert user

    # a product
    result = await connection.execute(
        products.insert()
        .values(random_product(group_id=None))
        .returning(sa.literal_column("*"))
    )
    product = await result.first()
    assert product

    # a price per product
    result = await connection.execute(
        products_prices.insert()
        .values(
            product_name=product.name,
            dollars_per_credit=100,
            authorized_by=user.id,
        )
        .returning(sa.literal_column("*"))
    )
    product_prices = await result.first()
    assert product_prices

    # check if the user is PO when the price is setup
