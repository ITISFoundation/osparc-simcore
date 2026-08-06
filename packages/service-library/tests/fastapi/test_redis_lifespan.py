# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from typing import Annotated, Any

import pytest
import servicelib.fastapi.redis_lifespan
from asgi_lifespan import LifespanManager as ASGILifespanManager
from fastapi import FastAPI
from fastapi_lifespan_manager import LifespanManager
from pydantic import Field
from pytest_mock import MockerFixture, MockType
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict
from pytest_simcore.helpers.typing_env import EnvVarsDict
from servicelib.fastapi.redis_lifespan import (
    configure_redis_client_sdk,
    configure_redis_clients_manager,
)
from servicelib.redis import RedisManagerDBConfig
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
    return setenvs_from_dict(monkeypatch, RedisSettings.model_json_schema()["examples"][0])


async def test_configure_redis_client_sdk_publishes_client_in_app_state(
    is_pdb_enabled: bool,
    app_environment: EnvVarsDict,
    mock_redis_client_sdk: MockType,
):
    assert app_environment

    class AppSettings(BaseApplicationSettings):
        CATALOG_REDIS: Annotated[
            RedisSettings,
            Field(json_schema_extra={"auto_default_from_env": True}),
        ]

    settings = AppSettings.create_from_envs()

    app_lifespan = LifespanManager()
    configure_redis_client_sdk(
        app_lifespan,
        settings=settings.CATALOG_REDIS,
        database=RedisDatabase.LOCKS,
        client_name="test_client",
    )

    app = FastAPI(lifespan=app_lifespan)

    async with ASGILifespanManager(
        app,
        startup_timeout=None if is_pdb_enabled else 10,
        shutdown_timeout=None if is_pdb_enabled else 10,
    ):
        mock_redis_client_sdk.assert_called_once_with(
            settings.CATALOG_REDIS.build_redis_dsn(RedisDatabase.LOCKS),
            client_name="test_client",
        )
        assert app.state.redis_client_sdk == mock_redis_client_sdk.return_value

    redis_client: Any = mock_redis_client_sdk.return_value
    redis_client.shutdown.assert_called_once()


async def test_configure_redis_clients_manager_has_clients_for_required_dbs(
    is_pdb_enabled: bool,
    app_environment: EnvVarsDict,
    mocker: MockerFixture,
):
    assert app_environment

    class AppSettings(BaseApplicationSettings):
        CATALOG_REDIS: Annotated[
            RedisSettings,
            Field(json_schema_extra={"auto_default_from_env": True}),
        ]

    settings = AppSettings.create_from_envs()

    required_dbs: set[RedisDatabase] = {
        RedisDatabase.LOCKS,
        RedisDatabase.CELERY_TASKS,
    }
    expected_dsn_by_db: dict[RedisDatabase, str] = {
        db: settings.CATALOG_REDIS.build_redis_dsn(db) for db in required_dbs
    }

    clients_by_db: dict[RedisDatabase, Any] = {}

    def _redis_client_factory(redis_dsn: str, **_: Any) -> Any:
        matching_db = next(db for db, dsn in expected_dsn_by_db.items() if dsn == redis_dsn)
        client = mocker.AsyncMock()
        client.is_healthy = True
        clients_by_db[matching_db] = client
        return client

    mocker.patch(
        "servicelib.redis._clients_manager.RedisClientSDK",
        side_effect=_redis_client_factory,
    )

    app_lifespan = LifespanManager()
    configure_redis_clients_manager(
        app_lifespan,
        settings=settings.CATALOG_REDIS,
        databases_configs={RedisManagerDBConfig(database=db) for db in required_dbs},
        client_name="test_manager",
    )

    app = FastAPI(lifespan=app_lifespan)

    async with ASGILifespanManager(
        app,
        startup_timeout=None if is_pdb_enabled else 10,
        shutdown_timeout=None if is_pdb_enabled else 10,
    ):
        manager = app.state.redis_clients_manager
        assert manager.healthy

        for db in required_dbs:
            client = manager.client(db)
            assert client == clients_by_db[db]

        assert set(clients_by_db) == required_dbs

    for client in clients_by_db.values():
        client.shutdown.assert_called_once()
