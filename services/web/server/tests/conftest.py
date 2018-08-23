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
import yaml

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


def _is_db_service_responsive(**pg_config):
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


@pytest.fixture(scope='session')
def docker_compose_file(package_paths):
    """
      Path to docker-compose configuration files used for testing

      - fixture defined in pytest-docker
    """
    fpath = package_paths.MOCK_FOLDER / 'docker-compose.yml'
    assert fpath.exists()
    return str(fpath)

@pytest.fixture(scope="session")
def server_test_file(package_paths):
    fpath = package_paths.CONFIG_FOLDER / "server-host-test.yaml"
    assert fpath.exists()
    return fpath

# TODO: extend Service object from pytest-docker

@pytest.fixture(scope="session")
def mock_services(docker_ip, docker_services, docker_compose_file, server_test_file):
    """
      services in mock/docker-compose.yml
    """

    with open(docker_compose_file) as stream:
        c = yaml.load(stream)
        for service_name in c["services"].keys():
            # pylint: disable=W0212
            docker_services._services.get(service_name, {})

    # Patches os.environ to influence
    pre_os_environ = os.environ.copy()
    os.environ["POSTGRES_PORT"] = str(docker_services.port_for('db', 5432))
    os.environ["RABBIT_HOST"] = str(docker_ip)

    # loads app config
    app_config = read_and_validate( server_test_file )
    pg_config = app_config["postgres"]

    # NOTE: this can be eventualy handled by the service under test as well!!
    docker_services.wait_until_responsive(
        check=lambda: _is_db_service_responsive(**pg_config),
        timeout=20.0,
        pause=1.0,
    )

    # start db & inject mockup data
    test_engine = acquire_engine(DNS.format(**pg_config))
    init_db.setup_db(pg_config)
    init_db.create_tables(test_engine)
    init_db.sample_data(test_engine)

    yield docker_services

    init_db.drop_tables(test_engine)
    init_db.teardown_db(pg_config)

    os.environ = pre_os_environ
