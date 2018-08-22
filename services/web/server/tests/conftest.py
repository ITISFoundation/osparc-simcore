"""

    pytest-docker https://github.com/AndreLouisCaron/pytest-docker
"""
# pylint: disable=unused-argument
# pylint: disable=unused-import
# pylint: disable=bare-except
# pylint: disable=W0621
import logging
import os
import pathlib
import sys
import collections

import pytest

import init_db
from server.db.utils import (
    DNS,
    acquire_admin_engine,
    acquire_engine
)
from server.settings import (
    read_and_validate
)


_LOGGER = logging.getLogger(__name__)
CURRENT_DIR = pathlib.Path(sys.argv[0] if __name__ == "__main__" else __file__).parent.absolute()



def _is_responsive(**pg_config):
    try:
        admin_engine = acquire_admin_engine(**pg_config)
        conn = admin_engine.connect()
        conn.close()
    except:
        _LOGGER.exception("Connection to db failed")
        return False
    return True

# extends pytest-docker -------------------------------------------------------

@pytest.fixture(scope='session')
def package_paths(pytestconfig):
    package_root = CURRENT_DIR.parent
    config_folder =  package_root / "config"
    test_folder = package_root / "tests"
    mock_folder = test_folder / "mock"

    paths={}
    paths["ROOT_FOLDER"] = package_root
    paths["CONFIG_FOLDER"] = config_folder
    paths["TEST_FOLDER"] = test_folder
    paths["MOCK_FOLDER"] = mock_folder

    for key, path in paths.items():
        assert path.exists(), "Invalid path in %s" % key

    return collections.namedtuple("PackagePaths", paths.keys())(**paths)

@pytest.fixture(scope="session")
def app_testconfig(package_paths):
    path = package_paths.CONFIG_FOLDER / "server-host-test.yaml"
    config = read_and_validate(path.as_posix())
    return config

@pytest.fixture(scope='session')
def docker_compose_file(package_paths):
    """
      Path to docker-compose configuration files used for testing

      - fixture defined in pytest-docker
    """
    return str(package_paths.MOCK_FOLDER / 'docker-compose.yml')

@pytest.fixture(scope="session")
def postgres_service(docker_ip, docker_services, app_testconfig):
    """
      starts postgress service with sample data
    """
    _LOGGER.debug("Started docker at %s:%d", docker_ip, docker_services.port_for('db', 5432))

    pg_config = app_testconfig["postgres"]

    test_engine = acquire_engine(DNS.format(**pg_config))

    docker_services.wait_until_responsive(
        check=lambda: _is_responsive(**pg_config),
        timeout=30.0,
        pause=1.0,
    )

    init_db.setup_db(pg_config)
    init_db.create_tables(test_engine)
    init_db.sample_data(test_engine)

    yield pg_config

    init_db.drop_tables(test_engine)
    init_db.teardown_db(pg_config)
