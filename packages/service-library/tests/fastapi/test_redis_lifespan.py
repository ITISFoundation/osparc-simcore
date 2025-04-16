# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from collections.abc import AsyncIterator
from typing import Annotated, Any

import pytest
import servicelib.fastapi.redis_lifespan
from asgi_lifespan import LifespanManager as ASGILifespanManager
from fastapi import FastAPI
from fastapi_lifespan_manager import LifespanManager, State
from pydantic import Field
from pytest_mock import MockerFixture, MockType
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict
from pytest_simcore.helpers.typing_env import EnvVarsDict
from servicelib.fastapi.redis_lifespan import (
    RedisConfigurationError,
    RedisLifespanState,
    redis_database_lifespan,
)
from settings_library.application import BaseApplicationSettings
from settings_library.redis import RedisDatabase, RedisSettings


@pytest.fixture
def mock_redis_client_sdk(mocker: MockerFixture) -> MockType:
    return mocker.patch.object(
        servicelib.fastapi.redis_lifespan,
        "RedisClientSDK",
        return_value=mocker.AsyncMock(),
    )


@pytest.fixture
def app_environment(monkeypatch: pytest.MonkeyPatch) -> EnvVarsDict:
    return setenvs_from_dict(
        monkeypatch, RedisSettings.model_json_schema()["examples"][0]
    )


@pytest.fixture
def app_lifespan(
    app_environment: EnvVarsDict,
    mock_redis_client_sdk: MockType,
) -> LifespanManager:
    assert app_environment

    class AppSettings(BaseApplicationSettings):
        CATALOG_REDIS: Annotated[
            RedisSettings,
            Field(json_schema_extra={"auto_default_from_env": True}),
        ]

    async def my_app_settings(app: FastAPI) -> AsyncIterator[State]:
        app.state.settings = AppSettings.create_from_envs()

        yield RedisLifespanState(
            REDIS_SETTINGS=app.state.settings.CATALOG_REDIS,
            REDIS_CLIENT_NAME="test_client",
            REDIS_CLIENT_DB=RedisDatabase.LOCKS,
        ).model_dump()

    app_lifespan = LifespanManager()
    app_lifespan.add(my_app_settings)
    app_lifespan.add(redis_database_lifespan)

    assert not mock_redis_client_sdk.called

    return app_lifespan


async def test_lifespan_redis_database_in_an_app(
    is_pdb_enabled: bool,
    app_environment: EnvVarsDict,
    mock_redis_client_sdk: MockType,
    app_lifespan: LifespanManager,
):
    app = FastAPI(lifespan=app_lifespan)

    async with ASGILifespanManager(
        app,
        startup_timeout=None if is_pdb_enabled else 10,
        shutdown_timeout=None if is_pdb_enabled else 10,
    ) as asgi_manager:
        # Verify that the Redis client SDK was created
        mock_redis_client_sdk.assert_called_once_with(
            app.state.settings.CATALOG_REDIS.build_redis_dsn(RedisDatabase.LOCKS),
            client_name="test_client",
        )

        # Verify that the Redis client SDK is in the lifespan manager state
        assert "REDIS_CLIENT_SDK" in asgi_manager._state  # noqa: SLF001
        assert app.state.settings.CATALOG_REDIS
        assert (
            asgi_manager._state["REDIS_CLIENT_SDK"]  # noqa: SLF001
            == mock_redis_client_sdk.return_value
        )

    # Verify that the Redis client SDK was shut down
    redis_client: Any = mock_redis_client_sdk.return_value
    redis_client.shutdown.assert_called_once()


async def test_lifespan_redis_database_with_invalid_settings(
    is_pdb_enabled: bool,
):
    async def my_app_settings(app: FastAPI) -> AsyncIterator[State]:
        yield {"REDIS_SETTINGS": None}

    app_lifespan = LifespanManager()
    app_lifespan.add(my_app_settings)
    app_lifespan.add(redis_database_lifespan)

    app = FastAPI(lifespan=app_lifespan)

    with pytest.raises(RedisConfigurationError, match="Invalid redis") as excinfo:
        async with ASGILifespanManager(
            app,
            startup_timeout=None if is_pdb_enabled else 10,
            shutdown_timeout=None if is_pdb_enabled else 10,
        ):
            ...

    exception = excinfo.value
    assert isinstance(exception, RedisConfigurationError)
    assert exception.validation_error
    assert exception.state["REDIS_SETTINGS"] is None
