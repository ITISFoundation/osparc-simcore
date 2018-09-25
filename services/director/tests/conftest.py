import pytest
import logging
from pathlib import Path
import sys

from simcore_service_director import (
    config,
    registry_proxy
    )
# pylint:disable=unused-argument

pytest_plugins = ["fixtures.docker_registry"]

_logger = logging.getLogger(__name__)
CURRENT_DIR = Path(sys.argv[0] if __name__ == "__main__" else __file__).parent.absolute()


@pytest.fixture(scope='session')
def docker_compose_file(pytestconfig):
    my_path = CURRENT_DIR / "docker-compose.yml"
    return my_path

@pytest.fixture
def configure_registry_access(docker_registry):
    config.REGISTRY_URL = docker_registry
    config.REGISTRY_SSL = False
    config.CONVERT_OLD_API = False
    registry_proxy.setup_registry_connection()