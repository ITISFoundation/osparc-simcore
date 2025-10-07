# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

from collections.abc import AsyncGenerator, AsyncIterator, Callable

import pytest
from asgi_lifespan import LifespanManager
from fastapi import FastAPI
from fastapi.security import HTTPBasicCredentials
from models_library.api_schemas_api_server.api_keys import ApiKeyInDB
from pydantic import PositiveInt
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


async def test_get_user_with_valid_credentials(
    create_fake_api_keys: Callable[[PositiveInt], AsyncGenerator[ApiKeyInDB, None]],
    api_key_repo: ApiKeysRepository,
):

    # Generate a fake API key
    async for api_key_in_db in create_fake_api_keys(1):
        # Act
        result = await api_key_repo.get_user(
            api_key=api_key_in_db.api_key, api_secret=api_key_in_db.api_secret
        )

        # Assert
        assert result is not None
        assert result.user_id == api_key_in_db.user_id
        assert result.product_name == api_key_in_db.product_name
        break


async def test_get_user_with_invalid_credentials(
    api_key_repo: ApiKeysRepository,
    create_fake_api_keys: Callable[[PositiveInt], AsyncGenerator[ApiKeyInDB, None]],
):

    # Generate a fake API key
    async for api_key_in_db in create_fake_api_keys(1):
        # Act - use wrong secret
        result = await api_key_repo.get_user(
            api_key=api_key_in_db.api_key, api_secret="wrong_secret"
        )

        # Assert
        assert result is None
        break


async def test_rest_dependency_authentication(
    api_key_repo: ApiKeysRepository,
    users_repo: UsersRepository,
    create_fake_api_keys: Callable[[PositiveInt], AsyncGenerator[ApiKeyInDB, None]],
):

    # Generate a fake API key
    async for api_key_in_db in create_fake_api_keys(1):
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
        break
