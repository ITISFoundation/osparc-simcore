# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

from collections.abc import AsyncIterable

import pytest
import sqlalchemy as sa
from aiopg.sa.connection import SAConnection
from aiopg.sa.result import RowProxy
from pytest_simcore.helpers import postgres_users
from pytest_simcore.helpers.faker_factories import (
    random_api_auth,
    random_product,
)
from simcore_postgres_database.models.api_keys import api_keys
from simcore_postgres_database.models.products import products
from simcore_postgres_database.models.users import users


@pytest.fixture
async def user_id(connection: SAConnection) -> AsyncIterable[int]:
    user_id = await postgres_users.insert_user_and_secrets(connection)

    assert user_id
    yield user_id

    await connection.execute(users.delete().where(users.c.id == user_id))


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
        .values(**random_api_auth(product_name, user_id))
        .returning(api_keys.c.id)
    )

    assert apikey_id
    assert apikey_id >= 1

    await connection.execute(api_keys.delete().where(api_keys.c.id == apikey_id))


@pytest.fixture
async def session_auth(
    connection: SAConnection, user_id: int, product_name: str
) -> AsyncIterable[RowProxy]:
    # user_id under product_name creates an api-key+secret and
    # uses to authenticate a session.
    result = await connection.execute(
        api_keys.insert()
        .values(**random_api_auth(product_name, user_id))
        .returning(sa.literal_column("*"))
    )
    row = await result.fetchone()
    assert row

    yield row

    await connection.execute(api_keys.delete().where(api_keys.c.id == row.id))


async def test_get_session_identity_for_api_server(
    connection: SAConnection, user_id: int, product_name: str, session_auth: RowProxy
):
    # NOTE: preview of what needs to implement api-server to authenticate and
    # authorize a session
    #
    result = await connection.execute(
        sa.select(
            api_keys.c.user_id,
            api_keys.c.product_name,
        ).where(
            (api_keys.c.api_key == session_auth.api_key)
            & (api_keys.c.api_secret == session_auth.api_secret),
        )
    )
    row = await result.fetchone()
    assert row

    # session identity
    assert row.user_id == user_id
    assert row.product_name == product_name
