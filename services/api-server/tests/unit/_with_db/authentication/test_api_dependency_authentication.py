# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

import time

import pytest
from fastapi.security import HTTPBasicCredentials
from models_library.api_schemas_api_server.api_keys import ApiKeyInDB
from pytest_mock import MockerFixture
from simcore_service_api_server.api.dependencies.authentication import (
    get_current_identity,
)
from simcore_service_api_server.repository.api_keys import ApiKeysRepository
from simcore_service_api_server.repository.users import UsersRepository


async def test_rest_dependency_authentication(
    api_key_in_db: ApiKeyInDB,
    api_key_repo: ApiKeysRepository,
    users_repo: UsersRepository,
):
    # Generate a fake API key
    # Act
    result = await get_current_identity(
        apikeys_repo=api_key_repo,
        users_repo=users_repo,
        credentials=HTTPBasicCredentials(username=api_key_in_db.api_key, password=api_key_in_db.api_secret),
    )

    # Assert
    assert result is not None
    assert result.user_id == api_key_in_db.user_id
    assert result.product_name == api_key_in_db.product_name


@pytest.mark.skip(reason="This test is intended to be used for local profiling only")
async def test_cache_effectiveness_in_rest_authentication_dependencies(
    api_key_in_db: ApiKeyInDB,
    api_key_repo: ApiKeysRepository,
    users_repo: UsersRepository,
    mocker: MockerFixture,
):
    """Test that caching reduces database calls and improves performance."""

    # Generate a fake API key
    credentials = HTTPBasicCredentials(username=api_key_in_db.api_key, password=api_key_in_db.api_secret)

    # Get cache instances from repository methods
    # pylint: disable=no-member
    api_keys_cache = api_key_repo.get_user.cache
    users_cache = users_repo.get_active_user_email.cache

    # Clear any existing cache
    await api_keys_cache.clear()
    await users_cache.clear()

    # Spy on the connection's execute method by patching AsyncConnection.execute
    from sqlalchemy.ext.asyncio import AsyncConnection  # noqa: PLC0415

    execute_spy = mocker.spy(AsyncConnection, "execute")

    # Test with cache enabled (default behavior)
    # First call - should hit database
    start_time = time.time()
    result1 = await get_current_identity(
        apikeys_repo=api_key_repo,
        users_repo=users_repo,
        credentials=credentials,
    )
    first_call_time = time.time() - start_time

    # Second call - should use cache
    start_time = time.time()
    result2 = await get_current_identity(
        apikeys_repo=api_key_repo,
        users_repo=users_repo,
        credentials=credentials,
    )
    second_call_time = time.time() - start_time

    cached_db_calls = execute_spy.call_count
    execute_spy.reset_mock()

    # Verify cache was used
    api_key_cache_key = f"api_auth:{api_key_in_db.api_key}"
    user_cache_key = f"user_email:{api_key_in_db.user_id}"

    assert await api_keys_cache.exists(api_key_cache_key), "API key should be cached"
    assert await users_cache.exists(user_cache_key), "User email should be cached"

    # Test with cache disabled by clearing cache before each call
    await api_keys_cache.clear()
    await users_cache.clear()

    # First call without cache
    start_time = time.time()
    result3 = await get_current_identity(
        apikeys_repo=api_key_repo,
        users_repo=users_repo,
        credentials=credentials,
    )
    no_cache_first_time = time.time() - start_time

    # Clear cache again to simulate no caching
    await api_keys_cache.clear()
    await users_cache.clear()

    # Second call without cache
    start_time = time.time()
    result4 = await get_current_identity(
        apikeys_repo=api_key_repo,
        users_repo=users_repo,
        credentials=credentials,
    )
    no_cache_second_time = time.time() - start_time

    no_cache_db_calls = execute_spy.call_count

    # ASSERTIONS
    # All results should be identical
    assert result1.user_id == result2.user_id == result3.user_id == result4.user_id
    assert result1.product_name == result2.product_name == result3.product_name == result4.product_name
    assert result1.email == result2.email == result3.email == result4.email

    # With cache: second call should be significantly faster
    assert second_call_time < first_call_time * 0.5, "Cache should make subsequent calls faster"

    # Without cache: both calls should take similar time
    time_ratio = abs(no_cache_second_time - no_cache_first_time) / max(no_cache_first_time, no_cache_second_time)
    assert time_ratio < 0.5, "Without cache, call times should be similar"

    # With cache: fewer total database calls (due to caching)
    # Without cache: more database calls (no caching)
    assert no_cache_db_calls > cached_db_calls, "Cache should reduce database calls"
