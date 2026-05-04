# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

from collections.abc import AsyncGenerator, AsyncIterator, Callable

import pytest
from asgi_lifespan import LifespanManager
from fastapi import FastAPI
from models_library.api_schemas_api_server.api_keys import ApiKeyInDB
from pydantic import PositiveInt
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
    create_fake_api_keys: Callable[[PositiveInt], AsyncGenerator[ApiKeyInDB]],
) -> ApiKeyInDB:
    """Creates a single API key in DB for testing purposes"""
    return await anext(create_fake_api_keys(1))
