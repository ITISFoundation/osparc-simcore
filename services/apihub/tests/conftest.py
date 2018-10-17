import logging
import sys
from pathlib import Path
import requests

import pytest

# pylint:disable=unused-argument
log = logging.getLogger(__name__)
CURRENT_DIR = Path(sys.argv[0] if __name__ == "__main__" else __file__).parent.absolute()


@pytest.fixture(scope='session')
def docker_compose_file(pytestconfig):
    my_path = CURRENT_DIR / "docker-compose.yml"
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