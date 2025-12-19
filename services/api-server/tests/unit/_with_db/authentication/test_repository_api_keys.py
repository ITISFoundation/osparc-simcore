# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


from models_library.api_schemas_api_server.api_keys import ApiKeyInDB
from simcore_service_api_server.repository.api_keys import ApiKeysRepository


async def test_get_user_with_valid_credentials(
    api_key_in_db: ApiKeyInDB,
    api_key_repo: ApiKeysRepository,
):
    # Act
    result = await api_key_repo.get_user(
        api_key=api_key_in_db.api_key, api_secret=api_key_in_db.api_secret
    )

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
    result = await api_key_repo.get_user(
        api_key=api_key_in_db.api_key, api_secret="wrong_secret"
    )

    # Assert
    assert result is None
