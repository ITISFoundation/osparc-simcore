from collections.abc import AsyncIterable

import pytest
from aiopg.sa.connection import SAConnection
from pytest_simcore.helpers.rawdata_fakers import (
    ramdom_api_key,
    random_product,
    random_user,
)
from simcore_postgres_database.models.api_keys import api_keys
from simcore_postgres_database.models.products import products
from simcore_postgres_database.models.users import users


@pytest.fixture
async def user_id(connection: SAConnection) -> AsyncIterable[int]:
    uid = await connection.scalar(
        users.insert().values(random_user()).returning(users.c.id)
    )
    assert uid
    yield uid

    await connection.execute(users.delete().where(users.c.id == uid))


@pytest.fixture
async def product_name(connection: SAConnection) -> AsyncIterable[str]:
    name = await connection.scalar(
        products.insert()
        .values(random_product(name="s4l", group_id=None))
        .returning(products.c.name)
    )
    assert name
    yield name

    await connection.execute(products.delete().where(products.c.name == name))


async def test_create_and_delete_api_key(
    connection: SAConnection, user_id: int, product_name: str
):
    apikey_id = await connection.scalar(
        api_keys.insert()
        .values(**ramdom_api_key(product_name, user_id))
        .returning(api_keys.c.id)
    )

    assert apikey_id
    assert apikey_id >= 1

    await connection.execute(api_keys.delete().where(api_keys.c.id == apikey_id))
