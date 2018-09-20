import pytest
import logging
from pathlib import Path
import sys
# pylint:disable=unused-argument

pytest_plugins = ["fixtures.docker_registry"]

_logger = logging.getLogger(__name__)
CURRENT_DIR = Path(sys.argv[0] if __name__ == "__main__" else __file__).parent.absolute()


@pytest.fixture(scope='session')
def docker_compose_file(pytestconfig):
    my_path = CURRENT_DIR / "docker-compose.yml"
    return my_path
