# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

from collections.abc import AsyncIterator
from typing import Final

import pytest
from asgi_lifespan import LifespanManager
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pytest_simcore.helpers.monkeypatch_envs import EnvVarsDict, setenvs_from_dict
from settings_library.rabbit import RabbitSettings
from settings_library.redis import RedisSettings
from simcore_service_notifications.core.application import create_app
from simcore_service_notifications.core.settings import ApplicationSettings

_LIFESPAN_TIMEOUT: Final[int] = 30


@pytest.fixture
def app_environment(
    monkeypatch: pytest.MonkeyPatch,
    mock_environment: EnvVarsDict,
) -> EnvVarsDict:
    return setenvs_from_dict(
        monkeypatch,
        {
            **mock_environment,
        },
    )


@pytest.fixture
def enabled_rabbitmq(
    app_environment: EnvVarsDict, rabbit_service: RabbitSettings
) -> RabbitSettings:
    return rabbit_service


@pytest.fixture
def enabled_redis(
    app_environment: EnvVarsDict, redis_service: RedisSettings
) -> RedisSettings:
    return redis_service


@pytest.fixture
def app_settings(
    app_environment: EnvVarsDict,
    enabled_rabbitmq: RabbitSettings,
    enabled_redis: RedisSettings,
) -> ApplicationSettings:
    settings = ApplicationSettings.create_from_envs()
    print(f"{settings.model_dump_json(indent=2)=}")
    return settings


@pytest.fixture
async def initialized_app(app_settings: ApplicationSettings) -> AsyncIterator[FastAPI]:
    app: FastAPI = create_app(app_settings)

    async with LifespanManager(app, startup_timeout=30, shutdown_timeout=30):
        yield app


@pytest.fixture
def test_client(initialized_app: FastAPI) -> TestClient:
    return TestClient(initialized_app)
