# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import os
import re
import shutil
import stat
from collections.abc import AsyncIterator, Callable
from pathlib import Path
from typing import Awaitable

import httpx
import pytest
import simcore_service_efs_guardian
import yaml
from asgi_lifespan import LifespanManager
from fakeredis.aioredis import FakeRedis
from fastapi import FastAPI
from httpx import ASGITransport
from pytest_mock import MockerFixture
from pytest_simcore.helpers.monkeypatch_envs import EnvVarsDict, setenvs_from_dict
from servicelib.rabbitmq import RabbitMQRPCClient
from settings_library.efs import AwsEfsSettings
from settings_library.rabbit import RabbitSettings
from simcore_service_efs_guardian.core.application import create_app
from simcore_service_efs_guardian.core.settings import ApplicationSettings

pytest_plugins = [
    "pytest_simcore.cli_runner",
    "pytest_simcore.docker_compose",
    "pytest_simcore.docker_registry",
    "pytest_simcore.docker_swarm",
    "pytest_simcore.environment_configs",
    "pytest_simcore.faker_projects_data",
    "pytest_simcore.pydantic_models",
    "pytest_simcore.pytest_global_environs",
    "pytest_simcore.rabbit_service",
    "pytest_simcore.redis_service",
    "pytest_simcore.repository_paths",
    "pytest_simcore.aws_s3_service",
    "pytest_simcore.aws_server",
]


@pytest.fixture(scope="session")
def project_slug_dir(osparc_simcore_root_dir: Path) -> Path:
    # fixtures in pytest_simcore.environs
    service_folder = osparc_simcore_root_dir / "services" / "efs_guardian"
    assert service_folder.exists()
    assert any(service_folder.glob("src/simcore_service_efs_guardian"))
    return service_folder


@pytest.fixture(scope="session")
def installed_package_dir() -> Path:
    dirpath = Path(simcore_service_efs_guardian.__file__).resolve().parent
    assert dirpath.exists()
    return dirpath


@pytest.fixture
def docker_compose_service_efs_guardian_env_vars(
    services_docker_compose_file: Path,
    env_devel_dict: EnvVarsDict,
) -> EnvVarsDict:
    """env vars injected at the docker-compose"""

    payments = yaml.safe_load(services_docker_compose_file.read_text())["services"][
        "efs-guardian"
    ]

    def _substitute(key, value):
        if m := re.match(r"\${([^{}:-]\w+)", value):
            expected_env_var = m.group(1)
            try:
                # NOTE: if this raises, then the RHS env-vars in the docker-compose are
                # not defined in the env-devel
                if value := env_devel_dict[expected_env_var]:
                    return key, value
            except KeyError:
                pytest.fail(
                    f"{expected_env_var} is not defined in .env-devel but used in docker-compose services[{payments}].environment[{key}]"
                )
        return None

    envs: EnvVarsDict = {}
    for key, value in payments.get("environment", {}).items():
        if found := _substitute(key, value):
            _, new_value = found
            envs[key] = new_value

    return envs


@pytest.fixture
def app_environment(
    monkeypatch: pytest.MonkeyPatch,
    docker_compose_service_efs_guardian_env_vars: EnvVarsDict,
) -> EnvVarsDict:
    return setenvs_from_dict(
        monkeypatch,
        {
            **docker_compose_service_efs_guardian_env_vars,
            "EFS_DNS_NAME": "fs-xxx.efs.us-east-1.amazonaws.com",
            "EFS_MOUNTED_PATH": "/tmp/efs",
            "EFS_PROJECT_SPECIFIC_DATA_DIRECTORY": "project-specific-data",
            "EFS_ONLY_ENABLED_FOR_USERIDS": "[]",
        },
    )


@pytest.fixture
def app_settings(app_environment: EnvVarsDict) -> ApplicationSettings:
    settings = ApplicationSettings.create_from_envs()
    return settings


@pytest.fixture
async def app(app_settings: ApplicationSettings) -> AsyncIterator[FastAPI]:
    the_test_app = create_app(app_settings)
    async with LifespanManager(
        the_test_app,
    ):
        yield the_test_app


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    # - Needed for app to trigger start/stop event handlers
    # - Prefer this client instead of fastapi.testclient.TestClient
    async with httpx.AsyncClient(
        app=app,
        base_url="http://efs-guardian.testserver.io",
        headers={"Content-Type": "application/json"},
    ) as client:
        assert isinstance(
            client._transport, ASGITransport  # pylint: disable=protected-access
        )
        yield client


@pytest.fixture
async def rpc_client(
    rabbit_service: RabbitSettings,
    app: FastAPI,
    rabbitmq_rpc_client: Callable[[str], Awaitable[RabbitMQRPCClient]],
) -> RabbitMQRPCClient:
    return await rabbitmq_rpc_client("client")


@pytest.fixture
async def mocked_redis_server(mocker: MockerFixture) -> None:
    mock_redis = FakeRedis()
    mocker.patch("redis.asyncio.from_url", return_value=mock_redis)


@pytest.fixture
async def cleanup(app: FastAPI):

    yield

    aws_efs_settings: AwsEfsSettings = app.state.settings.EFS_GUARDIAN_AWS_EFS_SETTINGS
    _dir_path = Path(aws_efs_settings.EFS_MOUNTED_PATH)
    if _dir_path.exists():
        for root, dirs, files in os.walk(_dir_path):
            for name in dirs + files:
                file_path = Path(root, name)
                # Get the current permissions of the file or directory
                current_permissions = Path.stat(file_path).st_mode
                # Add write permission for the owner (user)
                Path.chmod(file_path, current_permissions | stat.S_IWUSR)

        shutil.rmtree(_dir_path)
