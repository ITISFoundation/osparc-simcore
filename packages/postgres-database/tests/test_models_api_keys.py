# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

from collections.abc import AsyncIterable

import pytest
import sqlalchemy as sa
from pytest_simcore.helpers import postgres_users
from pytest_simcore.helpers.faker_factories import (
    random_api_auth,
    random_product,
)
from simcore_postgres_database.models.api_keys import api_keys
from simcore_postgres_database.models.products import products
from simcore_postgres_database.models.users import users
from sqlalchemy.engine.row import RowMapping
from sqlalchemy.ext.asyncio import AsyncConnection


@pytest.fixture
async def user_id(asyncpg_connection: AsyncConnection) -> AsyncIterable[int]:
    user_id = await postgres_users.insert_user_and_secrets(asyncpg_connection)

    assert user_id
    yield user_id

    await asyncpg_connection.execute(users.delete().where(users.c.id == user_id))


@pytest.fixture
async def product_name(asyncpg_connection: AsyncConnection) -> AsyncIterable[str]:
    name = await asyncpg_connection.scalar(
        products.insert().values(random_product(name="s4l", group_id=None)).returning(products.c.name)
    )
    assert name
    yield name

    await asyncpg_connection.execute(products.delete().where(products.c.name == name))


async def test_create_and_delete_api_key(asyncpg_connection: AsyncConnection, user_id: int, product_name: str):
    apikey_id = await asyncpg_connection.scalar(
        api_keys.insert().values(**random_api_auth(product_name, user_id)).returning(api_keys.c.id)
    )

    assert apikey_id
    assert apikey_id >= 1

    await asyncpg_connection.execute(api_keys.delete().where(api_keys.c.id == apikey_id))


@pytest.fixture
async def session_auth(
    asyncpg_connection: AsyncConnection, user_id: int, product_name: str
) -> AsyncIterable[RowMapping]:
    # user_id under product_name creates an api-key+secret and
    # uses to authenticate a session.
    result = await asyncpg_connection.execute(
        api_keys.insert().values(**random_api_auth(product_name, user_id)).returning(sa.literal_column("*"))
    )
    row = result.mappings().one()
    assert row

    yield row

    await asyncpg_connection.execute(api_keys.delete().where(api_keys.c.id == row["id"]))


async def test_get_session_identity_for_api_server(
    asyncpg_connection: AsyncConnection, user_id: int, product_name: str, session_auth: RowMapping
):
    # NOTE: preview of what needs to implement api-server to authenticate and
    # authorize a session
    #
    result = await asyncpg_connection.execute(
        sa.select(
            api_keys.c.user_id,
            api_keys.c.product_name,
        ).where(
            (api_keys.c.api_key == session_auth["api_key"]) & (api_keys.c.api_secret == session_auth["api_secret"]),
        )
    )
    row = result.mappings().one()
    assert row

    # session identity
    assert row["user_id"] == user_id
    assert row["product_name"] == product_name
