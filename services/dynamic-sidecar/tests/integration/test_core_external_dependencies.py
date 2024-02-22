# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
from unittest.mock import AsyncMock

import pytest
from async_asgi_testclient import TestClient
from fastapi import FastAPI
from models_library.projects import ProjectID
from models_library.users import UserID
from pytest_simcore.helpers.utils_envs import EnvVarsDict, setenvs_from_dict
from pytest_simcore.helpers.utils_postgres import PostgresTestConfig
from settings_library.rabbit import RabbitSettings
from simcore_service_dynamic_sidecar.core.application import create_app
from yarl import URL

pytest_simcore_core_services_selection = [
    "migration",
    "postgres",
    "rabbit",
    "storage",
]

pytest_simcore_ops_services_selection = [
    "minio",
]


@pytest.fixture
def mock_environment(
    postgres_host_config: PostgresTestConfig,
    storage_endpoint: URL,
    minio_s3_settings_envs: EnvVarsDict,
    rabbit_settings: RabbitSettings,
    monkeypatch: pytest.MonkeyPatch,
    base_mock_envs: EnvVarsDict,
    user_id: UserID,
    project_id: ProjectID,
) -> EnvVarsDict:
    assert storage_endpoint.host

    envs: EnvVarsDict = {
        "DY_SIDECAR_CALLBACKS_MAPPING": "{}",
        "DY_SIDECAR_PROJECT_ID": f"{project_id}",
        "DY_SIDECAR_USER_ID": f"{user_id}",
        "DYNAMIC_SIDECAR_LOG_LEVEL": "DEBUG",
        "R_CLONE_PROVIDER": "MINIO",
        "RABBIT_HOST": rabbit_settings.RABBIT_HOST,
        "RABBIT_PASSWORD": rabbit_settings.RABBIT_PASSWORD.get_secret_value(),
        "RABBIT_PORT": f"{rabbit_settings.RABBIT_PORT}",
        "RABBIT_SECURE": f"{rabbit_settings.RABBIT_SECURE}",
        "RABBIT_USER": rabbit_settings.RABBIT_USER,
        "STORAGE_HOST": storage_endpoint.host,
        "STORAGE_PORT": f"{storage_endpoint.port}",
        **base_mock_envs,
    }

    setenvs_from_dict(monkeypatch, envs)
    return envs


@pytest.fixture
def app(
    mock_environment: EnvVarsDict,
    mock_registry_service: AsyncMock,
) -> FastAPI:
    """creates app with registry and rabbitMQ services mocked"""
    return create_app()


async def test_external_dependencies_are_reachable(app: FastAPI):
    async with TestClient(app):
        # checks that client starts properly
        assert True
