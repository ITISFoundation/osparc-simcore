# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

import time
from collections.abc import AsyncGenerator, AsyncIterator, Callable

import pytest
from aiocache import Cache
from asgi_lifespan import LifespanManager
from fastapi import FastAPI
from fastapi.security import HTTPBasicCredentials
from models_library.api_schemas_api_server.api_keys import ApiKeyInDB
from pydantic import PositiveInt
from pytest_mock import MockerFixture
from simcore_service_api_server.api.dependencies.authentication import (
    get_current_identity,
)
from simcore_service_api_server.clients.postgres import get_engine
from simcore_service_api_server.repository.api_keys import ApiKeysRepository
from simcore_service_api_server.repository.users import UsersRepository
from sqlalchemy.ext.asyncio import AsyncEngine

MAX_TIME_FOR_APP_TO_STARTUP = 10
MAX_TIME_FOR_APP_TO_SHUTDOWN = 10


@pytest.fixture
async def app_started(app: FastAPI, is_pdb_enabled: bool) -> AsyncIterator[FastAPI]:
    # LifespanManager will trigger app's startup&shutown event handlers
    async with LifespanManager(
        app,
        startup_timeout=None if is_pdb_enabled else MAX_TIME_FOR_APP_TO_STARTUP,
        shutdown_timeout=None if is_pdb_enabled else MAX_TIME_FOR_APP_TO_SHUTDOWN,
    ):
        yield app


@pytest.fixture
async def async_engine(app_started: FastAPI) -> AsyncEngine:
    # Overrides
    return get_engine(app_started)


@pytest.fixture
def api_key_repo(
    async_engine: AsyncEngine,
) -> ApiKeysRepository:
    return ApiKeysRepository(db_engine=async_engine)


@pytest.fixture
def users_repo(
    async_engine: AsyncEngine,
) -> UsersRepository:
    return UsersRepository(db_engine=async_engine)


@pytest.fixture
async def api_key_in_db(
    create_fake_api_keys: Callable[[PositiveInt], AsyncGenerator[ApiKeyInDB, None]],
) -> ApiKeyInDB:
    """Creates a single API key in DB for testing purposes"""
    return await anext(create_fake_api_keys(1))


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
        credentials=HTTPBasicCredentials(
            username=api_key_in_db.api_key, password=api_key_in_db.api_secret
        ),
    )

    # Assert
    assert result is not None
    assert result.user_id == api_key_in_db.user_id
    assert result.product_name == api_key_in_db.product_name


async def test_cache_effectiveness_in_rest_authentication_dependencies(
    api_key_in_db: ApiKeyInDB,
    api_key_repo: ApiKeysRepository,
    users_repo: UsersRepository,
    monkeypatch: pytest.MonkeyPatch,
    mocker: MockerFixture,
):
    """Test that caching reduces database calls and improves performance."""

    # Generate a fake API key
    credentials = HTTPBasicCredentials(
        username=api_key_in_db.api_key, password=api_key_in_db.api_secret
    )

    # Test with cache enabled (default)
    monkeypatch.delenv("AIOCACHE_DISABLE", raising=False)
    await Cache().clear()  # Clear any existing cache

    # Spy on the connection's execute method by patching AsyncConnection.execute
    from sqlalchemy.ext.asyncio import AsyncConnection  # noqa: PLC0415

    execute_spy = mocker.spy(AsyncConnection, "execute")

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

    # Test with cache disabled
    monkeypatch.setenv("AIOCACHE_DISABLE", "1")

    # First call without cache
    start_time = time.time()
    result3 = await get_current_identity(
        apikeys_repo=api_key_repo,
        users_repo=users_repo,
        credentials=credentials,
    )
    no_cache_first_time = time.time() - start_time

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
    assert (
        result1.product_name
        == result2.product_name
        == result3.product_name
        == result4.product_name
    )
    assert result1.email == result2.email == result3.email == result4.email

    # With cache: second call should be significantly faster
    assert (
        second_call_time < first_call_time * 0.5
    ), "Cache should make subsequent calls faster"

    # Without cache: both calls should take similar time
    time_ratio = abs(no_cache_second_time - no_cache_first_time) / max(
        no_cache_first_time, no_cache_second_time
    )
    assert time_ratio < 0.5, "Without cache, call times should be similar"

    # With cache: fewer total database calls (due to caching)
    # Without cache: more database calls (no caching)
    assert no_cache_db_calls > cached_db_calls, "Cache should reduce database calls"
