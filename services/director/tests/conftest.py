# pylint: disable=unused-argument
# pylint: disable=unused-import
# pylint: disable=bare-except
# pylint: disable=redefined-outer-name

import logging
import os
import sys
from asyncio import Future
from pathlib import Path

import pytest

import simcore_service_director
from simcore_service_director import config, resources

pytest_plugins = ["fixtures.docker_registry", "fixtures.docker_swarm", "fixtures.fake_services"]

_logger = logging.getLogger(__name__)
CURRENT_DIR = Path(sys.argv[0] if __name__ == "__main__" else __file__).parent.absolute()

@pytest.fixture(scope='session')
def here():
    return Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent

@pytest.fixture(scope='session')
def osparc_simcore_root_dir(here):
    root_dir = here.parent.parent.parent.resolve()
    assert root_dir.exists(), "Is this service within osparc-simcore repo?"
    assert any(root_dir.glob("services/web/server")), "%s not look like rootdir" % root_dir
    return root_dir

@pytest.fixture(scope='session')
def docker_compose_file(pytestconfig, here):
    my_path = here / "docker-compose.yml"
    return my_path

@pytest.fixture(scope='session')
def api_specs_dir(osparc_simcore_root_dir):
    specs_dir = osparc_simcore_root_dir/ "api" / "specs" / "director"
    assert specs_dir.exists()
    return specs_dir

@pytest.fixture(scope='session')
def shared_schemas_specs_dir(osparc_simcore_root_dir):
    specs_dir = osparc_simcore_root_dir/ "api" / "specs" / "shared" / "schemas"
    assert specs_dir.exists()
    return specs_dir

@pytest.fixture(scope='session')
def package_dir(here):
    dirpath = Path(simcore_service_director.__file__).resolve().parent
    assert dirpath.exists()
    return dirpath

@pytest.fixture
def configure_schemas_location(package_dir, shared_schemas_specs_dir):
    config.NODE_SCHEMA_LOCATION = str(shared_schemas_specs_dir / "node-meta-v0.0.1.json")
    resources.RESOURCE_NODE_SCHEMA = os.path.relpath(config.NODE_SCHEMA_LOCATION, package_dir)


@pytest.fixture
def configure_registry_access(docker_registry):
    config.REGISTRY_URL = docker_registry
    config.REGISTRY_SSL = False
    config.REGISTRY_CACHING = False

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
    config.REGISTRY_CACHING = False

@pytest.fixture
async def aiohttp_mock_app(loop, mocker):
    aiohttp_mock_app = mocker.patch('aiohttp.web.Application')
    return aiohttp_mock_app

@pytest.fixture
async def aiodocker_mock_network(loop, mocker):
    aiodocker_mock_network = mocker.patch('aiodocker.networks.DockerNetwork')
    aiodocker_mock_network.return_value.id = None
    aiodocker_mock_network.return_value.delete.return_value = Future()
    aiodocker_mock_network.return_value.delete.return_value.set_result("")
    return aiodocker_mock_network

@pytest.fixture
async def mock_connect(loop, mocker):
    mock_connect_to_network = mocker.patch('simcore_service_director.producer._connect_service_to_network')
    mock_connect_to_network.return_value = Future()
    mock_connect_to_network.return_value.set_result("")
    return mock_connect_to_network

@pytest.fixture
async def mock_get_service_id(loop, mocker):
    get_service_mock = mocker.patch('simcore_service_director.producer._get_service_container_name')
    get_service_mock.return_value = Future()
    get_service_mock.return_value.set_result("")
    return get_service_mock
