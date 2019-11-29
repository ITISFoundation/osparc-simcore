""" Configuration for unit testing with a postgress fixture

    - Unit testing of webserver app with a postgress service as fixture
    - Starts test session by running a postgres container as a fixture (see postgress_service)

    IMPORTANT: remember that these are still unit-tests!
"""
# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import os
import sys
from asyncio import Future
from copy import deepcopy
from pathlib import Path

import pytest
import sqlalchemy as sa
import trafaret_config

import simcore_service_webserver.utils
from simcore_service_webserver.application import create_application
from simcore_service_webserver.application_config import \
    app_schema as app_schema
from simcore_service_webserver.db import DSN
from simcore_service_webserver.db_models import confirmations, metadata, users

## current directory
current_dir = Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent


@pytest.fixture(scope="session")
def default_app_cfg(osparc_simcore_root_dir, fake_static_dir):
    # NOTE: ONLY used at the session scopes
    cfg_path = current_dir / "config.yaml"
    assert cfg_path.exists()

    variables = dict(os.environ)
    variables.update({
        'OSPARC_SIMCORE_REPO_ROOTDIR': str(osparc_simcore_root_dir),
    })

    # validates and fills all defaults/optional entries that normal load would not do
    cfg_dict = trafaret_config.read_and_validate(cfg_path, app_schema, vars=variables)

    assert Path(cfg_dict["main"]["client_outdir"]) == fake_static_dir

    # WARNING: changes to this fixture during testing propagates to other tests. Use cfg = deepcopy(cfg_dict)
    # FIXME:  free cfg_dict but deepcopy shall be r/w
    return cfg_dict

@pytest.fixture(scope="function")
def app_cfg(default_app_cfg, aiohttp_unused_port):
    cfg = deepcopy(default_app_cfg)

    # fills ports on the fly
    cfg["main"]["port"] = aiohttp_unused_port()
    cfg["storage"]["port"] = aiohttp_unused_port()

    # this fixture can be safely modified during test since it is renovated on every call
    return cfg

@pytest.fixture(scope='session')
def docker_compose_file(default_app_cfg):
    """ Overrides pytest-docker fixture

    """
    old = os.environ.copy()

    cfg = deepcopy(default_app_cfg["db"]["postgres"])

    # docker-compose reads these environs
    os.environ['TEST_POSTGRES_DB']=cfg['database']
    os.environ['TEST_POSTGRES_USER']=cfg['user']
    os.environ['TEST_POSTGRES_PASSWORD']=cfg['password']

    dc_path = current_dir / 'docker-compose.yml'

    assert dc_path.exists()
    yield str(dc_path)

    os.environ = old


@pytest.fixture(scope='session')
def postgres_service(docker_services, docker_ip, default_app_cfg):
    cfg = deepcopy(default_app_cfg["db"]["postgres"])
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
def postgres_db(app_cfg, postgres_service):
    cfg = app_cfg["db"]["postgres"]
    url_from_cfg = DSN.format(**cfg)

    url = postgres_service or url_from_cfg

    # Configures db and initializes tables
    # Uses syncrounous engine for that
    engine = sa.create_engine(url, isolation_level="AUTOCOMMIT")
    metadata.create_all(bind=engine, tables=[users, confirmations], checkfirst=True)

    yield engine

    metadata.drop_all(engine)
    engine.dispose()

@pytest.fixture
def web_server(loop, aiohttp_server, app_cfg, monkeypatch, postgres_db):
    app = create_application(app_cfg)
    path_mail(monkeypatch)
    server = loop.run_until_complete( aiohttp_server(app, port=app_cfg["main"]["port"]) )
    return server

@pytest.fixture
def client(loop, aiohttp_client, web_server):
    client = loop.run_until_complete(aiohttp_client(web_server))
    return client

@pytest.fixture
async def storage_subsystem_mock(loop, mocker):
    """
        Patches client calls to storage service

        Patched functions are exposed within projects but call storage subsystem
    """
    # requests storage to copy data
    mock = mocker.patch('simcore_service_webserver.projects.projects_api.copy_data_folders_from_project')
    async def _mock_copy_data_from_project(*args):
        return args[2]

    mock.side_effect = _mock_copy_data_from_project

    # requests storage to delete data
    #mock1 = mocker.patch('simcore_service_webserver.projects.projects_handlers.delete_data_folders_of_project', return_value=None)
    mock1 = mocker.patch('simcore_service_webserver.projects.projects_handlers.projects_api.delete_data_folders_of_project', return_value=Future())
    mock1.return_value.set_result("")
    return mock, mock1


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
