import logging
import os

import psycopg2

import pytest
from pytest_docker import docker_ip, docker_services  # pylint:disable=W0611

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import server.utils.init_db as init_db

_LOGGER = logging.getLogger(__name__)

#@pytest.fixture(scope='session')
#def docker_compose_file(pytestconfig):
#    """
#      Path to docker-compose configuration files used for testing
#    """
#    return os.path.join(
#        str(pytestconfig.rootdir),
#        '..'
#        'docker-compose.yml'
#    )


def is_responsive2(database, user, password, host, port, **kargs):
    """Check if there is a db"""
    try:
        conn = psycopg2.connect(
            dbname=database, user=user, password=password, host=host, port=port)
        conn.close()
    except psycopg2.OperationalError as _ex:
        logging.exception("Connection to db failed")
        return False

    return True

def is_responsive(**kargs):
  try:
    conn = init_db.admin_engine.connect()
    conn.close()
  except:
    logging.exception("Connection to db failed")
    return False
  return True


@pytest.fixture(scope="session")
def postgres_service(docker_ip, docker_services):
    """
      starts postgress service with sample data
    """
    config = init_db.TEST_CONFIG['postgres']
    engine = init_db.test_engine

    docker_services.wait_until_responsive(
        check=lambda: is_responsive(**config),
        timeout=30.0,
        pause=1.0,
    )

    init_db.setup_db(config)
    init_db.create_tables(engine)
    init_db.sample_data(engine)

    yield config

    init_db.drop_tables()
    init_db.teardown_db(config)

