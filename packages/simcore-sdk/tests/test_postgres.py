import logging

import psycopg2
import pytest
# pylint:disable=unused-import
from pytest_docker import docker_ip, docker_services

# pylint:disable=redefined-outer-name

def is_responsive(dbname, user, password, host, port):
    """Check if there is a db"""
    try:
        conn = psycopg2.connect(dbname=dbname, user=user, password=password, host=host, port=port)
        conn.close()
    except psycopg2.OperationalError as _ex:
        logging.exception("Connection to db failed")
        return False

    return True

@pytest.mark.enable_travis
def test_postgres(docker_ip, docker_services):
    """wait for postgres to be up"""

    dbname = 'test'
    user = 'user'
    password = 'pwd'
    host = docker_ip
    port = docker_services.port_for('postgres', 5432)
    # Wait until we can connect
    docker_services.wait_until_responsive(
        check=lambda: is_responsive(dbname, user, password, host, port),
        timeout=30.0,
        pause=1.0,
    )

    connection_ok = False
    try:
        conn = psycopg2.connect(dbname=dbname, user=user, password=password, host=host, port=port)
        conn.close()
        connection_ok = True
    except psycopg2.OperationalError as _ex:
        pass

    assert connection_ok
