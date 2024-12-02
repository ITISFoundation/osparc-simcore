# pylint:disable=redefined-outer-name
# pylint:disable=unused-argument

import string
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Final

import pytest
import simcore_service_dynamic_scheduler
import yaml
from asgi_lifespan import LifespanManager
from fastapi import FastAPI
from pytest_mock import MockerFixture
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict
from pytest_simcore.helpers.typing_env import EnvVarsDict
from servicelib.redis import RedisClientsManager, RedisManagerDBConfig
from servicelib.utils import logged_gather
from settings_library.redis import RedisDatabase, RedisSettings
from simcore_service_dynamic_scheduler.core.application import create_app

pytest_plugins = [
    "pytest_simcore.cli_runner",
    "pytest_simcore.docker_compose",
    "pytest_simcore.docker_swarm",
    "pytest_simcore.environment_configs",
    "pytest_simcore.faker_projects_data",
    "pytest_simcore.rabbit_service",
    "pytest_simcore.redis_service",
    "pytest_simcore.repository_paths",
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
        except (KeyError, ValueError) as err:
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
        {
            **docker_compose_service_dynamic_scheduler_env_vars,
            "DYNAMIC_SCHEDULER_TRACING": "null",
        },
    )


_PATH_APPLICATION: Final[str] = "simcore_service_dynamic_scheduler.core.application"


@pytest.fixture
def disable_rabbitmq_setup(mocker: MockerFixture) -> None:
    mocker.patch(f"{_PATH_APPLICATION}.setup_rabbitmq")
    mocker.patch(f"{_PATH_APPLICATION}.setup_rpc_api_routes")


@pytest.fixture
def disable_redis_setup(mocker: MockerFixture) -> None:
    mocker.patch(f"{_PATH_APPLICATION}.setup_redis")


@pytest.fixture
def disable_service_tracker_setup(mocker: MockerFixture) -> None:
    mocker.patch(f"{_PATH_APPLICATION}.setup_service_tracker")


@pytest.fixture
def disable_deferred_manager_setup(mocker: MockerFixture) -> None:
    mocker.patch(f"{_PATH_APPLICATION}.setup_deferred_manager")


@pytest.fixture
def disable_notifier_setup(mocker: MockerFixture) -> None:
    mocker.patch(f"{_PATH_APPLICATION}.setup_notifier")


@pytest.fixture
def disable_status_monitor_setup(mocker: MockerFixture) -> None:
    mocker.patch(f"{_PATH_APPLICATION}.setup_status_monitor")


MAX_TIME_FOR_APP_TO_STARTUP: Final[float] = 10
MAX_TIME_FOR_APP_TO_SHUTDOWN: Final[float] = 10


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


@pytest.fixture
async def remove_redis_data(redis_service: RedisSettings) -> None:
    async with RedisClientsManager(
        {RedisManagerDBConfig(x) for x in RedisDatabase},
        redis_service,
        client_name="pytest",
    ) as manager:
        await logged_gather(
            *[manager.client(d).redis.flushall() for d in RedisDatabase]
        )
