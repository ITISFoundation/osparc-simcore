"""

    pytest-docker https://github.com/AndreLouisCaron/pytest-docker
"""
# pylint: disable=unused-argument
# pylint: disable=unused-import
# pylint: disable=bare-except

import logging
import os

import pytest

import init_db

_LOGGER = logging.getLogger(__name__)
_CDIR = os.path.dirname(__file__)

def _is_responsive(**kargs):
    try:
        admin_engine = init_db.AdminEngine("localhost")
        conn = admin_engine.connect()
        conn.close()
    except:
        _LOGGER.exception("Connection to db failed")
        return False
    return True


# extends pytest-docker -------------------------------------------------------
@pytest.fixture(scope='session')
def docker_compose_file(pytestconfig):
    """
      Path to docker-compose configuration files used for testing

      - fixture defined in pytest-docker
    """
    return os.path.join(
        _CDIR,
        'mock',
        'docker-compose.yml')

@pytest.fixture(scope="session")
def postgres_service(docker_ip, docker_services):
    """
      starts postgress service with sample data
    """
    _LOGGER.debug("Started docker at %s:%d", docker_ip, docker_services.port_for('db', 5432))

    config = init_db.TEST_CONFIG
    pg_config = config['postgres']
    engine = init_db.test_engine

    docker_services.wait_until_responsive(
        check=lambda: _is_responsive(**pg_config),
        timeout=30.0,
        pause=1.0,
    )

    init_db.setup_db(pg_config)
    init_db.create_tables(engine)
    init_db.sample_data(engine)

    yield config

    init_db.drop_tables()
    init_db.teardown_db(pg_config)
