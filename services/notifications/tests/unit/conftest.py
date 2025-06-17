# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

from collections.abc import AsyncIterator

import pytest
import sqlalchemy as sa
from asgi_lifespan import LifespanManager
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pytest_simcore.helpers.monkeypatch_envs import EnvVarsDict, setenvs_from_dict
from settings_library.rabbit import RabbitSettings
from simcore_service_notifications.core.application import create_app


@pytest.fixture
def app_environment(
    monkeypatch: pytest.MonkeyPatch,
    mock_environment: EnvVarsDict,
    rabbit_service: RabbitSettings,
    postgres_db: sa.engine.Engine,  # waiting for postgres service to start
    postgres_env_vars_dict: EnvVarsDict,
) -> EnvVarsDict:
    return setenvs_from_dict(
        monkeypatch,
        {
            **mock_environment,
            "RABBIT_HOST": rabbit_service.RABBIT_HOST,
            "RABBIT_PASSWORD": rabbit_service.RABBIT_PASSWORD.get_secret_value(),
            "RABBIT_PORT": f"{rabbit_service.RABBIT_PORT}",
            "RABBIT_SECURE": f"{rabbit_service.RABBIT_SECURE}",
            "RABBIT_USER": rabbit_service.RABBIT_USER,
            **postgres_env_vars_dict,
        },
    )


@pytest.fixture
async def initialized_app(app_environment: EnvVarsDict) -> AsyncIterator[FastAPI]:
    app: FastAPI = create_app()

    async with LifespanManager(app, startup_timeout=30, shutdown_timeout=30):
        yield app


@pytest.fixture
def test_client(initialized_app: FastAPI) -> TestClient:
    return TestClient(initialized_app)
