# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


import datetime as dt
from collections.abc import AsyncGenerator, Callable

from models_library.api_schemas_api_server.api_keys import ApiKeyInDB
from simcore_service_api_server.repository.api_keys import ApiKeysRepository

pytest_simcore_core_services_selection = ["postgres"]


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
    create_fake_api_keys: Callable[..., AsyncGenerator[ApiKeyInDB]],
    api_key_repo: ApiKeysRepository,
):
    expired_key = await anext(create_fake_api_keys(1, expires_at=dt.datetime.now(dt.UTC) - dt.timedelta(days=1)))

    result = await api_key_repo.get_user(api_key=expired_key.api_key, api_secret=expired_key.api_secret)

    assert result is None


async def test_get_user_with_api_key_expiring_in_the_future(
    create_fake_api_keys: Callable[..., AsyncGenerator[ApiKeyInDB]],
    api_key_repo: ApiKeysRepository,
):
    future_key = await anext(create_fake_api_keys(1, expires_at=dt.datetime.now(dt.UTC) + dt.timedelta(days=1)))

    result = await api_key_repo.get_user(api_key=future_key.api_key, api_secret=future_key.api_secret)

    assert result is not None


async def test_cached_success_is_not_replayed_for_a_different_secret(
    api_key_in_db: ApiKeyInDB,
    api_key_repo: ApiKeysRepository,
):
    result = await api_key_repo.get_user(api_key=api_key_in_db.api_key, api_secret=api_key_in_db.api_secret)
    assert result is not None

    replay = await api_key_repo.get_user(api_key=api_key_in_db.api_key, api_secret="wrong_secret")  # noqa: S106
    assert replay is None
