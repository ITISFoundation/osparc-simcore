import logging
import os

import pytest
import sqlalchemy as sa
from pytest_docker import docker_ip, docker_services  # pylint:disable=W0611
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

#
# FIXME: this should be in sync with the original
# which is owned by the webserver???
_metadata = sa.MetaData()
_tokens = sa.Table("tokens", _metadata,
    sa.Column("token_id", sa.BigInteger, nullable=False, primary_key=True),
    sa.Column("user_id", sa.BigInteger, nullable=False),
    sa.Column("token_service", sa.String, nullable=False),
    sa.Column("token_data", sa.JSON, nullable=False),
)


def is_responsive(url):
    """Check if there is a db"""
    try:
        eng = sa.create_engine(url)
        conn = eng.connect()
        conn.close()
    except sa.exc.OperationalError:
        logging.exception("Connection to db failed")
        return False

    return True

# pylint:disable=redefined-outer-name
@pytest.fixture(scope="module")
def engine(docker_ip, docker_services):
    dbname = 'test'
    user = 'user'
    password = 'pwd'
    host = docker_ip
    port = docker_services.port_for('postgres', 5432)
    url = 'postgresql://{user}:{password}@{host}:{port}/{database}'.format(
        user = user,
        password = password,
        database = dbname,
        host=docker_ip,
        port=docker_services.port_for('postgres', 5432),
    )
    # Wait until we can connect
    docker_services.wait_until_responsive(
        check=lambda: is_responsive(url),
        timeout=30.0,
        pause=1.0,
    )

    # Configures db and initializes tables
    # Uses syncrounous engine for that
    engine = create_engine(url, client_encoding='utf8')
    _metadata.create_all(bind=engine, tables=[_tokens, ], checkfirst=True)

    os.environ["POSTGRES_ENDPOINT"]="{host}:{port}".format(host=host, port=port)
    os.environ["POSTGRES_USER"]="user"
    os.environ["POSTGRES_PASSWORD"]="pwd"
    os.environ["POSTGRES_DB"]="test"
    yield engine
    # cleanup
    engine.dispose()



# pylint:disable=redefined-outer-name
@pytest.fixture(scope="module")
def session(engine):
    Session = sessionmaker(engine)
    session = Session()

    yield session
    #cleanup
    session.close()
