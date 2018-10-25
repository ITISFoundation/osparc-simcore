# pylint:disable=wildcard-import
# pylint:disable=unused-import
# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name


import os
import sys
from pathlib import Path

import pytest
import sqlalchemy as sa
import trafaret_config
import yaml

import simcore_service_webserver.utils
from simcore_service_webserver.application import create_application
from simcore_service_webserver.db import DSN
from simcore_service_webserver.db_models import confirmations, metadata, users
from simcore_service_webserver.settings import CONFIG_SCHEMA


@pytest.fixture(scope="session")
def here():
    return Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent

@pytest.fixture(scope="session")
def app_cfg(here):
    cfg_path = here / "config.yaml"
    assert cfg_path.exists()

    # validates and fills all defaults/optional entries that normal load would not do
    cfg_dict = trafaret_config.read_and_validate(cfg_path, CONFIG_SCHEMA)
    return cfg_dict

@pytest.fixture(scope='session')
def docker_compose_file(here, app_cfg):
    """ Overrides pytest-docker fixture
    """
    old = os.environ.copy()

    cfg = app_cfg["postgres"]

    # docker-compose reads these environs
    os.environ['TEST_POSTGRES_DB']=cfg['database']
    os.environ['TEST_POSTGRES_USER']=cfg['user']
    os.environ['TEST_POSTGRES_PASSWORD']=cfg['password']

    dc_path = here / 'docker-compose.yml'

    assert dc_path.exists()
    yield str(dc_path)

    os.environ = old

@pytest.fixture(scope='session')
def postgres_service(docker_services, docker_ip, app_cfg):
    cfg = app_cfg["postgres"]
    cfg['host'] = docker_ip
    cfg['port'] = docker_services.port_for('postgres', 5432)

    url = DSN.format(**cfg)

    # Wait until service is responsive.
    docker_services.wait_until_responsive(
        check=lambda: is_postgres_responsive(url),
        timeout=30.0,
        pause=0.1,
    )

    return url

@pytest.fixture
def postgres_db(app_cfg, postgres_service): # NOTE: if postgres_services started manually, comment
    """
        For debugging, postgres_service can be started manually as
            docker-compose -f docker-compose.debug.yml up

        In that case, comment postgres_service)
    """
    cfg = app_cfg["postgres"]
    url = DSN.format(**cfg)

    # NOTE: Comment this to avoid postgres_service
    url = postgres_service

    # Configures db and initializes tables
    # Uses syncrounous engine for that
    engine = sa.create_engine(url, isolation_level="AUTOCOMMIT")
    metadata.create_all(bind=engine, tables=[users, confirmations], checkfirst=True)

    yield engine

    metadata.drop_all(engine)
    engine.dispose()

@pytest.fixture
def server(loop, aiohttp_server, app_cfg, monkeypatch, aiohttp_unused_port, postgres_db): #pylint: disable=R0913
    port = app_cfg["main"]["port"] = aiohttp_unused_port()

    app = create_application(app_cfg)
    path_mail(monkeypatch)
    server = loop.run_until_complete( aiohttp_server(app, port=port) )
    return server

@pytest.fixture
def client(loop, aiohttp_client, server):
    client = loop.run_until_complete(aiohttp_client(server))
    return client




# helpers ---------------
def path_mail(monkeypatch):
    async def send_mail(*args):
        print('=== EMAIL TO: {}\n=== SUBJECT: {}\n=== BODY:\n{}'.format(*args))

    monkeypatch.setattr(simcore_service_webserver.login.utils, 'send_mail', send_mail)

def is_postgres_responsive(url):
    """Check if something responds to ``url`` """
    try:
        engine = sa.create_engine(url)
        conn = engine.connect()
        conn.close()
    except sa.exc.OperationalError:
        return False
    return True
