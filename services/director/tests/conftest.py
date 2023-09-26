# pylint: disable=unused-argument
# pylint: disable=unused-import
# pylint: disable=bare-except
# pylint: disable=redefined-outer-name

import os
from pathlib import Path

import pytest
import simcore_service_director
from aiohttp import ClientSession
from simcore_service_director import config, resources

# NOTE: that all the changes in these pytest-plugins MUST by py3.6 compatible!
pytest_plugins = [
    "fixtures.fake_services",
    "pytest_simcore.docker_compose",
    "pytest_simcore.docker_registry",
    "pytest_simcore.docker_swarm",
    "pytest_simcore.repository_paths",
    "pytest_simcore.tmp_path_extra",
    "pytest_simcore.pytest_global_environs",
]


@pytest.fixture
def configure_swarm_stack_name():
    config.SWARM_STACK_NAME = "test_stack"


@pytest.fixture(scope="session")
def common_schemas_specs_dir(osparc_simcore_root_dir):
    specs_dir = osparc_simcore_root_dir / "api" / "specs" / "director" / "schemas"
    assert specs_dir.exists()
    return specs_dir


@pytest.fixture(scope="session")
def package_dir():
    dirpath = Path(simcore_service_director.__file__).resolve().parent
    assert dirpath.exists()
    return dirpath


@pytest.fixture
def configure_schemas_location(package_dir, common_schemas_specs_dir):
    config.NODE_SCHEMA_LOCATION = str(
        common_schemas_specs_dir / "node-meta-v0.0.1.json"
    )
    resources.RESOURCE_NODE_SCHEMA = os.path.relpath(
        config.NODE_SCHEMA_LOCATION, package_dir
    )


@pytest.fixture
def configure_registry_access(docker_registry):
    config.REGISTRY_URL = docker_registry
    config.REGISTRY_PATH = docker_registry
    config.REGISTRY_SSL = False
    config.DIRECTOR_REGISTRY_CACHING = False


@pytest.fixture
def user_id():
    yield "some_user_id"


@pytest.fixture
def project_id():
    yield "some_project_id"


def pytest_addoption(parser):
    parser.addoption("--registry_url", action="store", default="default url")
    parser.addoption("--registry_user", action="store", default="default user")
    parser.addoption("--registry_pw", action="store", default="default pw")


@pytest.fixture(scope="session")
def configure_custom_registry(pytestconfig):
    # to set these values call
    # pytest --registry_url myregistry --registry_user username --registry_pw password
    config.REGISTRY_URL = pytestconfig.getoption("registry_url")
    config.REGISTRY_AUTH = True
    config.REGISTRY_USER = pytestconfig.getoption("registry_user")
    config.REGISTRY_PW = pytestconfig.getoption("registry_pw")
    config.DIRECTOR_REGISTRY_CACHING = False


@pytest.fixture
async def aiohttp_mock_app(loop, mocker):
    print("client session started ...")
    session = ClientSession()

    mock_app_storage = {
        config.APP_CLIENT_SESSION_KEY: session,
        config.APP_REGISTRY_CACHE_DATA_KEY: {},
    }

    def _get_item(self, key):
        return mock_app_storage[key]

    aiohttp_app = mocker.patch("aiohttp.web.Application")
    aiohttp_app.__getitem__ = _get_item

    yield aiohttp_app

    # cleanup session
    await session.close()
    print("client session closed")


@pytest.fixture
def api_version_prefix() -> str:
    assert "v0" in resources.listdir(resources.RESOURCE_OPENAPI_ROOT)
    return "v0"
