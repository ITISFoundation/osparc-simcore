# pylint: disable=not-context-manager
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from typing import AsyncIterable
from unittest import mock

import httpx
import pytest
import sqlalchemy as sa
from asgi_lifespan import LifespanManager
from fastapi import FastAPI
from pytest import MonkeyPatch
from pytest_mock import MockerFixture
from pytest_simcore.helpers.typing_env import EnvVarsDict
from pytest_simcore.helpers.utils_envs import setenvs_from_dict
from simcore_service_resource_usage_tracker.core.application import create_app
from simcore_service_resource_usage_tracker.core.settings import ApplicationSettings


@pytest.fixture(scope="function")
def mock_env(monkeypatch: MonkeyPatch) -> EnvVarsDict:
    """This is the base mock envs used to configure the app.

    Do override/extend this fixture to change configurations
    """
    env_vars: EnvVarsDict = {
        "SC_BOOT_MODE": "production",
        "POSTGRES_CLIENT_NAME": "postgres_test_client",
    }
    setenvs_from_dict(monkeypatch, env_vars)
    return env_vars


@pytest.fixture(scope="function")
async def initialized_app(
    mock_env: EnvVarsDict,
    postgres_db: sa.engine.Engine,
    postgres_host_config: dict[str, str],
) -> AsyncIterable[FastAPI]:
    settings = ApplicationSettings.create_from_envs()
    app = create_app(settings)
    async with LifespanManager(app):
        yield app


@pytest.fixture(scope="function")
async def async_client(initialized_app: FastAPI) -> AsyncIterable[httpx.AsyncClient]:
    async with httpx.AsyncClient(
        app=initialized_app,
        base_url="http://resource-usage-tracker.testserver.io",
        headers={"Content-Type": "application/json"},
    ) as client:
        yield client


@pytest.fixture
def mocked_prometheus(mocker: MockerFixture) -> mock.Mock:
    mocked_get_prometheus_api_client = mocker.patch(
        "simcore_service_resource_usage_tracker.resource_tracker_core.get_prometheus_api_client",
        autospec=True,
    )
    return mocked_get_prometheus_api_client
