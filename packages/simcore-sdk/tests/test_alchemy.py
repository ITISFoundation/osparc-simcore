import logging

import psycopg2
import pytest
# pylint:disable=unused-import
from pytest_docker import docker_ip, docker_services
from sqlalchemy import JSON, Column, Integer, String, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm.attributes import flag_modified

# pylint:disable=redefined-outer-name


BASE = declarative_base()
class User(BASE):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    name = Column(String)
    data = Column(JSON)


def is_responsive(dbname, user, password, host, port):
    """Check if there is a db"""
    try:
        conn = psycopg2.connect(dbname=dbname, user=user, password=password, host=host, port=port)
        conn.close()
    except psycopg2.OperationalError as _ex:
        logging.exception("Connection to db failed")
        return False

    return True

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

    def fin():
        engine.dispose()
    request.addfinalizer(fin)
    return engine

@pytest.fixture(scope="module")
def session(engine, request):
    Session = sessionmaker(engine)
    session = Session()

    def fin():
        session.close()

    request.addfinalizer(fin)
    return session

@pytest.mark.enable_travis
def test_alchemy(engine, session):
    BASE.metadata.create_all(engine)
    users = ['alpha', 'beta', 'gamma']
    
    for u in users:
        data = {}
        data['counter'] = 0
        user = User(name=u, data=data)
        session.add(user)
        session.commit()

    users2 = session.query(User).all()
    assert len(users2) == len(users)

    alpha = session.query(User).filter(User.name == 'alpha').one()

    assert alpha

    assert alpha.data['counter'] == 0
    alpha.data['counter'] = 42
    flag_modified(alpha, "data")
    session.commit()

    alpha2 = session.query(User).filter(User.name == 'alpha').one()
    assert alpha2.data['counter'] == 42
