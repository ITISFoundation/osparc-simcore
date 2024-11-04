# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

import os
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
import simcore_service_director
from asgi_lifespan import LifespanManager
from fastapi import FastAPI
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict
from pytest_simcore.helpers.typing_env import EnvVarsDict
from simcore_service_director import config, resources
from simcore_service_director.core.application import create_app
from simcore_service_director.core.settings import ApplicationSettings

pytest_plugins = [
    "fixtures.fake_services",
    "pytest_simcore.cli_runner",
    "pytest_simcore.docker_compose",
    "pytest_simcore.docker_registry",
    "pytest_simcore.docker_swarm",
    "pytest_simcore.environment_configs",
    "pytest_simcore.faker_projects_data",
    "pytest_simcore.faker_users_data",
    "pytest_simcore.repository_paths",
]


def pytest_addoption(parser):
    parser.addoption("--registry_url", action="store", default="default url")
    parser.addoption("--registry_user", action="store", default="default user")
    parser.addoption("--registry_pw", action="store", default="default pw")


@pytest.fixture(scope="session")
def project_slug_dir(osparc_simcore_root_dir: Path) -> Path:
    # fixtures in pytest_simcore.environs
    service_folder = osparc_simcore_root_dir / "services" / "director"
    assert service_folder.exists()
    assert any(service_folder.glob("src/simcore_service_director"))
    return service_folder


@pytest.fixture(scope="session")
def installed_package_dir() -> Path:
    dirpath = Path(simcore_service_director.__file__).resolve().parent
    assert dirpath.exists()
    return dirpath


@pytest.fixture(scope="session")
def common_schemas_specs_dir(osparc_simcore_root_dir: Path) -> Path:
    specs_dir = osparc_simcore_root_dir / "api" / "specs" / "director" / "schemas"
    assert specs_dir.exists()
    return specs_dir


@pytest.fixture
def configure_schemas_location(
    installed_package_dir: Path, common_schemas_specs_dir: Path
) -> None:
    config.NODE_SCHEMA_LOCATION = str(
        common_schemas_specs_dir / "node-meta-v0.0.1.json"
    )
    resources.RESOURCE_NODE_SCHEMA = os.path.relpath(
        config.NODE_SCHEMA_LOCATION, installed_package_dir
    )


@pytest.fixture(scope="session")
def configure_swarm_stack_name() -> None:
    config.SWARM_STACK_NAME = "test_stack"


@pytest.fixture
def configure_registry_access(docker_registry: str) -> None:
    config.REGISTRY_URL = docker_registry
    config.REGISTRY_PATH = docker_registry
    config.REGISTRY_SSL = False
    config.DIRECTOR_REGISTRY_CACHING = False


@pytest.fixture(scope="session")
def configure_custom_registry(pytestconfig: pytest.Config) -> None:
    # to set these values call
    # pytest --registry_url myregistry --registry_user username --registry_pw password
    config.REGISTRY_URL = pytestconfig.getoption("registry_url")
    config.REGISTRY_AUTH = True
    config.REGISTRY_USER = pytestconfig.getoption("registry_user")
    config.REGISTRY_PW = pytestconfig.getoption("registry_pw")
    config.DIRECTOR_REGISTRY_CACHING = False


@pytest.fixture
def api_version_prefix() -> str:
    assert "v0" in resources.listdir(resources.RESOURCE_OPENAPI_ROOT)
    return "v0"


@pytest.fixture
def app_environment(
    monkeypatch: pytest.MonkeyPatch,
    docker_compose_service_environment_dict: EnvVarsDict,
) -> EnvVarsDict:
    return setenvs_from_dict(
        monkeypatch,
        {
            **docker_compose_service_environment_dict,
            # ADD here env-var overrides
        },
    )


MAX_TIME_FOR_APP_TO_STARTUP = 10
MAX_TIME_FOR_APP_TO_SHUTDOWN = 10


@pytest.fixture
async def app(
    app_environment: EnvVarsDict, is_pdb_enabled: bool
) -> AsyncIterator[FastAPI]:
    the_test_app = create_app(settings=ApplicationSettings.create_from_envs())
    async with LifespanManager(
        the_test_app,
        startup_timeout=None if is_pdb_enabled else MAX_TIME_FOR_APP_TO_STARTUP,
        shutdown_timeout=None if is_pdb_enabled else MAX_TIME_FOR_APP_TO_SHUTDOWN,
    ):
        yield the_test_app


# @pytest.fixture
# async def aiohttp_mock_app(loop, mocker):
#     print("client session started ...")
#     session = ClientSession()

#     mock_app_storage = {
#         config.APP_CLIENT_SESSION_KEY: session,
#         config.APP_REGISTRY_CACHE_DATA_KEY: {},
#     }

#     def _get_item(self, key):
#         return mock_app_storage[key]

#     aiohttp_app = mocker.patch("aiohttp.web.Application")
#     aiohttp_app.__getitem__ = _get_item

#     yield aiohttp_app

#     # cleanup session
#     await session.close()
