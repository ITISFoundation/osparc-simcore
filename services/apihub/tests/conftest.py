# pylint: disable=unused-argument
# pylint: disable=redefined-outer-name
# pylint: disable=unused-variable
import logging
import sys
from pathlib import Path
from os.path import relpath
import pytest
import requests
from collections import namedtuple


SHARED = 'shared'
OPENAPI_MAIN_FILENAME = 'openapi.yaml'

log = logging.getLogger(__name__)


@pytest.fixture(scope='session')
def here():
    return Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent

@pytest.fixture(scope='session')
def osparc_simcore_root_dir(here):
    root_dir = here.parent.parent.parent
    assert root_dir.exists(), "Is this service within osparc-simcore repo?"
    assert any( root_dir.glob('services') )
    return root_dir


@pytest.fixture(scope='session')
def osparc_simcore_api_specs(osparc_simcore_root_dir):
    apis_dir = osparc_simcore_root_dir / "api" / "specs"
    assert apis_dir.exists()

    service_dirs = [d for d in apis_dir.iterdir() if d.is_dir() and not d.name.endswith(SHARED)]

    info_cls = namedtuple("Info", "service version openapi_path url_path".split())
    info = []
    for srv_dir in service_dirs:
        version_dirs = [d for d in srv_dir.iterdir() if d.is_dir() and not d.name.endswith(SHARED)]
        for ver_dir in version_dirs:
            openapi_path = ver_dir / OPENAPI_MAIN_FILENAME
            if openapi_path.exists():
                info.append( info_cls(
                    service=srv_dir.name,
                    version=ver_dir.name,
                    openapi_path=openapi_path,
                    url_path=relpath(openapi_path, osparc_simcore_root_dir) # api/specs/${service}/${version}/openapi.yaml
                ))
    # https://yarl.readthedocs.io/en/stable/api.html#yarl.URL
    # [scheme:]//[user[:password]@]host[:port][/path][?query][#fragment]
    return info


@pytest.fixture(scope='session')
def docker_compose_file(here, pytestconfig):
    my_path = here / "docker-compose.yml"
    return my_path


@pytest.fixture(scope="session")
def apihub(docker_ip, docker_services):
    host = docker_ip
    port = docker_services.port_for('apihub', 8043)
    url = "http://{host}:{port}".format(host=host, port=port)

    docker_services.wait_until_responsive(
        check=lambda: is_responsive(url),
        timeout=30.0,
        pause=1.0,
    )

    yield url

    log.debug("teardown apihub")


# utils ----

def is_responsive(url):
    # api = "{url}/api/specs/director/v0/openapi.yaml".format(url=url)
    r = requests.get(url)
    if r.status_code != 200:
        log.debug("Error while accessing the apihub")
        return False
    return True
