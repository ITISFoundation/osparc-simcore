# pylint: disable=W0621
# pylint:disable=unused-argument

import logging
import sys
from pathlib import Path
import requests

import pytest

log = logging.getLogger(__name__)



@pytest.fixture(scope='session')
def here():
    return Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent

@pytest.fixture(scope='session')
def osparc_simcore_root_dir(here):
    root_dir = here.parent.parent.parent
    assert root_dir.exists(), "Is this service within osparc-simcore repo?"
    assert "services" in root_dir.glob("*")
    return root_dir

@pytest.fixture(scope='session')
def simcore_apis_dir(osparc_simcore_root_dir):
    apis_dir = osparc_simcore_root_dir / "apis"
    assert apis_dir.exists()
    return apis_dir

@pytest.fixture(scope='session')
def docker_compose_file(here, pytestconfig):
    my_path = here / "docker-compose.yml"
    return my_path

def is_responsive(url):
    # api = "{url}/apis/director/v0/openapi.yaml".format(url=url)
    r = requests.get(url)
    if r.status_code != 200:
        log.debug("Error while accessing the apihub")
        return False
    return True

# pylint:disable=redefined-outer-name
@pytest.fixture(scope="session")
def apihub(docker_ip, docker_services):
    host = docker_ip
    port = docker_services.port_for('apihub', 8043)
    url = "http://{host}:{port}".format(host=host, port=port)
    # Wait until we can connect
    docker_services.wait_until_responsive(
        check=lambda: is_responsive(url),
        timeout=30.0,
        pause=1.0,
    )

    yield url
    print("teardown apihub")
