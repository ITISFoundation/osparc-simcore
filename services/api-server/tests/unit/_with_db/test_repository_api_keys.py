from collections.abc import AsyncGenerator, Callable

from models_library.api_schemas_api_server.api_keys import ApiKeyInDB
from pydantic import PositiveInt
from simcore_service_api_server.repository.api_keys import ApiKeysRepository
from sqlalchemy.ext.asyncio import AsyncEngine


async def test_get_user_with_valid_credentials(
    async_engine: AsyncEngine,
    create_fake_api_keys: Callable[[PositiveInt], AsyncGenerator[ApiKeyInDB, None]],
):
    # Arrange
    repo = ApiKeysRepository(db_engine=async_engine)

    # Generate a fake API key
    async for api_key_in_db in create_fake_api_keys(1):
        # Act
        result = await repo.get_user(
            api_key=api_key_in_db.api_key, api_secret=api_key_in_db.api_secret
        )

        # Assert
        assert result is not None
        assert result.user_id == api_key_in_db.user_id
        assert result.product_name == api_key_in_db.product_name
        break


async def test_get_user_with_invalid_credentials(
    async_engine: AsyncEngine,
    create_fake_api_keys: Callable[[PositiveInt], AsyncGenerator[ApiKeyInDB, None]],
):
    # Arrange
    repo = ApiKeysRepository(db_engine=async_engine)

    # Generate a fake API key
    async for api_key_in_db in create_fake_api_keys(1):
        # Act - use wrong secret
        result = await repo.get_user(
            api_key=api_key_in_db.api_key, api_secret="wrong_secret"
        )

        # Assert
        assert result is None
        break
