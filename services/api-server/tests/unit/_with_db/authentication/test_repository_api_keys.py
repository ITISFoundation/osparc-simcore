# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


import datetime as dt
from collections.abc import AsyncGenerator, Awaitable, Callable

import pytest
import sqlalchemy as sa
from models_library.api_schemas_api_server.api_keys import ApiKeyInDB
from pydantic import PositiveInt
from pytest_simcore.helpers.faker_factories import random_api_auth
from simcore_postgres_database.models.api_keys import api_keys
from simcore_service_api_server.repository.api_keys import ApiKeysRepository
from sqlalchemy.ext.asyncio import AsyncEngine

pytest_simcore_core_services_selection = ["postgres"]


@pytest.fixture
async def create_api_key_with_expiration(
    async_engine: AsyncEngine,
    create_user_ids: Callable[[PositiveInt], AsyncGenerator[int]],
    create_product_names: Callable[[PositiveInt], AsyncGenerator[str]],
) -> AsyncGenerator[Callable[[dt.datetime | None], Awaitable[tuple[str, str]]]]:
    """Inserts an API key with the given expires_at, returning (api_key, plain api_secret)"""
    created_ids: list[int] = []

    async def _create(expires_at: dt.datetime | None) -> tuple[str, str]:
        user_id = await anext(create_user_ids(1))
        product_name = await anext(create_product_names(1))
        api_auth = random_api_auth(product_name, user_id, expires_at=expires_at)
        plain_api_secret = api_auth.pop("api_secret")
        async with async_engine.begin() as conn:
            row = (
                await conn.execute(
                    api_keys.insert()
                    .values(
                        api_secret=sa.func.crypt(plain_api_secret, sa.func.gen_salt("bf", 10)),
                        **api_auth,
                    )
                    .returning(api_keys.c.id)
                )
            ).one()
        created_ids.append(row.id)
        return api_auth["api_key"], plain_api_secret

    yield _create

    async with async_engine.begin() as conn:
        await conn.execute(api_keys.delete().where(api_keys.c.id.in_(created_ids)))


async def test_get_user_with_valid_credentials(
    api_key_in_db: ApiKeyInDB,
    api_key_repo: ApiKeysRepository,
):
    # Act
    result = await api_key_repo.get_user(api_key=api_key_in_db.api_key, api_secret=api_key_in_db.api_secret)

    # Assert
    assert result is not None
    assert result.user_id == api_key_in_db.user_id
    assert result.product_name == api_key_in_db.product_name


async def test_get_user_with_invalid_credentials(
    api_key_in_db: ApiKeyInDB,
    api_key_repo: ApiKeysRepository,
):
    # Generate a fake API key

    # Act - use wrong secret
    result = await api_key_repo.get_user(api_key=api_key_in_db.api_key, api_secret="wrong_secret")  # noqa: S106

    # Assert
    assert result is None


async def test_get_user_with_expired_api_key(
    create_api_key_with_expiration: Callable[[dt.datetime | None], Awaitable[tuple[str, str]]],
    api_key_repo: ApiKeysRepository,
):
    api_key, api_secret = await create_api_key_with_expiration(dt.datetime.now(dt.UTC) - dt.timedelta(days=1))

    result = await api_key_repo.get_user(api_key=api_key, api_secret=api_secret)

    assert result is None


async def test_get_user_with_api_key_expiring_in_the_future(
    create_api_key_with_expiration: Callable[[dt.datetime | None], Awaitable[tuple[str, str]]],
    api_key_repo: ApiKeysRepository,
):
    expires_at = dt.datetime.now(dt.UTC) + dt.timedelta(days=1)
    api_key, api_secret = await create_api_key_with_expiration(expires_at)

    result = await api_key_repo.get_user(api_key=api_key, api_secret=api_secret)

    assert result is not None


async def test_get_user_without_expiration_never_expires(
    create_api_key_with_expiration: Callable[[dt.datetime | None], Awaitable[tuple[str, str]]],
    api_key_repo: ApiKeysRepository,
):
    api_key, api_secret = await create_api_key_with_expiration(None)

    result = await api_key_repo.get_user(api_key=api_key, api_secret=api_secret)

    assert result is not None
