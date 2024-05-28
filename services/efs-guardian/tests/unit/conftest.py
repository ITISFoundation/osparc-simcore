# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

from pathlib import Path
from typing import AsyncIterator

import httpx
import pytest
from asgi_lifespan import LifespanManager
from faker import Faker
from fastapi import FastAPI
from pytest import MonkeyPatch
from pytest_simcore.helpers.utils_envs import EnvVarsDict, setenvs_from_dict
from simcore_service_efs_guardian.core.application import create_app
from simcore_service_efs_guardian.core.settings import ApplicationSettings

pytest_plugins = [
    "pytest_simcore.cli_runner",
    "pytest_simcore.environment_configs",
    "pytest_simcore.repository_paths",
]


@pytest.fixture(scope="session")
def project_slug_dir(osparc_simcore_root_dir: Path) -> Path:
    # fixtures in pytest_simcore.environs
    service_folder = osparc_simcore_root_dir / "services" / "resource-usage-tracker"
    assert service_folder.exists()
    assert any(service_folder.glob("src/simcore_service_resource_usage_tracker"))
    return service_folder


@pytest.fixture
def app_environment(monkeypatch: MonkeyPatch, faker: Faker) -> EnvVarsDict:
    envs = setenvs_from_dict(
        monkeypatch,
        {
            "POSTGRES_HOST": faker.domain_name(),
            "POSTGRES_USER": faker.user_name(),
            "POSTGRES_PASSWORD": faker.password(),
            "POSTGRES_DB": faker.pystr(),
        },
    )

    return envs


@pytest.fixture
def app_settings(app_environment: EnvVarsDict) -> ApplicationSettings:
    settings = ApplicationSettings.create_from_envs()
    return settings


@pytest.fixture
async def initialized_app(app_settings: ApplicationSettings) -> AsyncIterator[FastAPI]:
    app = create_app(app_settings)
    async with LifespanManager(app):
        yield app


@pytest.fixture
async def async_client(initialized_app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    async with httpx.AsyncClient(
        app=initialized_app,
        base_url=f"http://{initialized_app.title}.testserver.io",
        headers={"Content-Type": "application/json"},
    ) as client:
        yield client
