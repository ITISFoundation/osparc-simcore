# pylint:disable=redefined-outer-name
# pylint:disable=unused-argument

import string
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
import simcore_service_dynamic_scheduler
import yaml
from asgi_lifespan import LifespanManager
from fastapi import FastAPI
from pytest_mock import MockerFixture
from pytest_simcore.helpers.typing_env import EnvVarsDict
from pytest_simcore.helpers.utils_envs import setenvs_from_dict
from simcore_service_dynamic_scheduler.core.application import create_app

pytest_plugins = [
    "pytest_simcore.cli_runner",
    "pytest_simcore.docker_compose",
    "pytest_simcore.docker_swarm",
    "pytest_simcore.environment_configs",
    "pytest_simcore.rabbit_service",
    "pytest_simcore.redis_service",
    "pytest_simcore.repository_paths",
    "pytest_simcore.tmp_path_extra",
]


@pytest.fixture(scope="session")
def project_slug_dir(osparc_simcore_root_dir: Path) -> Path:
    # fixtures in pytest_simcore.environs
    service_folder = osparc_simcore_root_dir / "services" / "dynamic-scheduler"
    assert service_folder.exists()
    assert any(service_folder.glob("src/simcore_service_dynamic_scheduler"))
    return service_folder


@pytest.fixture(scope="session")
def installed_package_dir() -> Path:
    dirpath = Path(simcore_service_dynamic_scheduler.__file__).resolve().parent
    assert dirpath.exists()
    return dirpath


@pytest.fixture
def docker_compose_service_dynamic_scheduler_env_vars(
    services_docker_compose_file: Path,
    env_devel_dict: EnvVarsDict,
) -> EnvVarsDict:
    """env vars injected at the docker-compose"""
    content = yaml.safe_load(services_docker_compose_file.read_text())
    environment = content["services"]["dynamic-schdlr"].get("environment", {})

    envs: EnvVarsDict = {}
    for name, value in environment.items():
        try:
            envs[name] = string.Template(value).substitute(env_devel_dict)
        except (KeyError, ValueError) as err:  # noqa: PERF203
            pytest.fail(
                f"{err}: {value} is not defined in .env-devel but used as RHS in docker-compose services['dynamic-schdlr'].environment[{name}]"
            )
    return envs


@pytest.fixture
def app_environment(
    monkeypatch: pytest.MonkeyPatch,
    docker_compose_service_dynamic_scheduler_env_vars: EnvVarsDict,
) -> EnvVarsDict:
    return setenvs_from_dict(
        monkeypatch,
        {**docker_compose_service_dynamic_scheduler_env_vars},
    )


@pytest.fixture
def disable_rabbitmq_setup(mocker: MockerFixture) -> None:
    base_path = "simcore_service_dynamic_scheduler.core.application"
    mocker.patch(f"{base_path}.setup_rabbitmq")
    mocker.patch(f"{base_path}.setup_rpc_api_routes")


@pytest.fixture
def disable_redis_setup(mocker: MockerFixture) -> None:
    base_path = "simcore_service_dynamic_scheduler.core.application"
    mocker.patch(f"{base_path}.setup_redis")


MAX_TIME_FOR_APP_TO_STARTUP = 10
MAX_TIME_FOR_APP_TO_SHUTDOWN = 10


@pytest.fixture
async def app(
    app_environment: EnvVarsDict, is_pdb_enabled: bool
) -> AsyncIterator[FastAPI]:
    test_app = create_app()
    async with LifespanManager(
        test_app,
        startup_timeout=None if is_pdb_enabled else MAX_TIME_FOR_APP_TO_STARTUP,
        shutdown_timeout=None if is_pdb_enabled else MAX_TIME_FOR_APP_TO_SHUTDOWN,
    ):
        yield test_app
