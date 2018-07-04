import logging
import os

import psycopg2
import pytest
from pytest_docker import docker_ip, docker_services  # pylint:disable=W0611
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


def is_responsive(dbname, user, password, host, port):
    """Check if there is a db"""
    try:
        conn = psycopg2.connect(dbname=dbname, user=user, password=password, host=host, port=port)
        conn.close()
    except psycopg2.OperationalError as _ex:
        logging.exception("Connection to db failed")
        return False

    return True

# pylint:disable=redefined-outer-name
@pytest.fixture(scope="module")
def engine(docker_ip, docker_services, request): 
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
    endpoint = 'postgresql+psycopg2://{user}:{password}@{host}:{port}/{dbname}'.format(
        user=user, password=password, host=host, port=port, dbname=dbname)
    engine = create_engine(endpoint, client_encoding='utf8')

    os.environ["POSTGRES_ENDPOINT"]="{host}:{port}".format(host=host, port=port)
    os.environ["POSTGRES_USER"]="user"
    os.environ["POSTGRES_PASSWORD"]="pwd"
    os.environ["POSTGRES_DB"]="test"

    def fin():
        engine.dispose()
    request.addfinalizer(fin)
    return engine

# pylint:disable=redefined-outer-name
@pytest.fixture(scope="module")
def session(engine, request):
    Session = sessionmaker(engine)
    session = Session()

    def fin():
        session.close()

    request.addfinalizer(fin)
    return session
