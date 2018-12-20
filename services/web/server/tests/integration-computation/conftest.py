
""" Tests computation within an environment having a
    - director service
    - celery
    - apihub service
"""
# pylint:disable=wildcard-import
# pylint:disable=unused-import
# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import os
import sys
from copy import deepcopy
from pathlib import Path
from typing import Dict

import pytest
import sqlalchemy as sa
import trafaret_config
import yaml

from simcore_service_webserver.application_config import app_schema
from simcore_service_webserver.cli import create_environ
from simcore_service_webserver.db import DSN
from simcore_service_webserver.db_models import confirmations, metadata, users
from simcore_service_webserver.resources import resources as app_resources
from simcore_sdk.models.pipeline_models import Base

SERVICES = ['director', 'apihub', 'rabbit', 'postgres', 'sidecar', 'storage', 'minio']


@pytest.fixture(scope="session")
def here() -> Path:
    return Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent


@pytest.fixture(scope='session')
def osparc_simcore_root_dir(here) -> Path:
    root_dir = here.parent.parent.parent.parent.parent.resolve()
    assert root_dir.exists(), "Is this service within osparc-simcore repo?"
    assert any(root_dir.glob("services/web/server")), "%s not look like rootdir" % root_dir
    return root_dir


@pytest.fixture("session")
def env_devel_file(osparc_simcore_root_dir) -> Path:
    env_devel_fpath = osparc_simcore_root_dir / ".env-devel"
    assert env_devel_fpath.exists()
    return env_devel_fpath


@pytest.fixture("session")
def services_docker_compose(osparc_simcore_root_dir) -> Dict[str, str]:
    docker_compose_path = osparc_simcore_root_dir / "services" / "docker-compose.yml"
    assert docker_compose_path.exists()

    content = {}
    with docker_compose_path.open() as f:
        content = yaml.safe_load(f)
    return content


@pytest.fixture("session")
def devel_environ(env_devel_file) -> Dict[str, str]:
    """ Environ dict from .env-devel """
    env_devel = {}
    with env_devel_file.open() as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                key, value = line.split("=")
                env_devel[key] = str(value)
    # ensure the test runs not as root if not under linux
    if 'RUN_DOCKER_ENGINE_ROOT' in env_devel:
        env_devel['RUN_DOCKER_ENGINE_ROOT'] = '0' if os.name == 'posix' else '1'
    return env_devel


@pytest.fixture(scope="session")
def webserver_environ(devel_environ, services_docker_compose) -> Dict[str, str]:
    """ Environment variables for the webserver application

    """
    dockerfile_environ = {'SIMCORE_WEB_OUTDIR': "undefined" } # TODO: parse webserver dockerfile ??

    service = services_docker_compose['services']['webserver']
    docker_compose_environ = resolve_environ(service, devel_environ)

    environ = {}
    environ.update(dockerfile_environ)
    environ.update(docker_compose_environ)

    # OVERRIDES:
    #   One of the biggest differences with respect to the real system
    #   is that the webserver application is replaced by a light-weight
    #   version tha loads only the subsystems under test. For that reason,
    #   the test webserver is built-up in webserver_service fixture that runs
    #   on the host.
    environ['DIRECTOR_HOST'] = '127.0.0.1'
    environ['POSTGRES_HOST'] = '127.0.0.1'
    environ['STORAGE_HOST'] = '127.0.0.1'
    environ['APIHUB_HOST'] = '127.0.0.1'

    return environ


@pytest.fixture(scope='session')
def app_config(here, webserver_environ) -> Dict:
    config_file_path = here / "config.yaml"
    def _recreate_config_file():
        with app_resources.stream("config/server-docker-dev.yaml") as f:
            cfg = yaml.safe_load(f)
            # test webserver works in host
            cfg["main"]['host'] = '127.0.0.0'
            cfg["rabbit"]["host"] = '127.0.0.1'
            cfg["rabbit"]["port"] = "5672"
            cfg["director"]["host"] = "127.0.0.1"

        with config_file_path.open('wt') as f:
            yaml.dump(cfg, f, default_flow_style=False)

    _recreate_config_file()

    # Emulates cli
    config_environ = {}
    config_environ.update(webserver_environ)
    config_environ.update( create_environ(skip_host_environ=True) ) # TODO: can be done monkeypathcing os.environ and calling create_environ as well

    # validates
    cfg_dict = trafaret_config.read_and_validate(config_file_path, app_schema, vars=config_environ)

    return cfg_dict


## EXTERNAL SERVICES ------------------------------------------------------------

@pytest.fixture(scope='session')
def docker_compose_file(here, services_docker_compose, devel_environ):
    """ Overrides pytest-docker fixture

    """
    docker_compose_path = here / 'docker-compose.yml'

    def _recreate_compose_file():
        # reads service/docker-compose.yml
        content = deepcopy(services_docker_compose)

        # remove unnecessary services
        keep = SERVICES
        remove = [name for name in content['services'] if name not in keep]
        for name in remove:
            content['services'].pop(name, None)

        for name in keep:
            service = content['services'][name]
            # remove builds
            if "build" in service:
                service.pop("build", None)
                service['image'] = "services_{}:latest".format(name)
            # replaces environs
            if "environment" in service:
                _environs = {}
                for item in service["environment"]:
                    key, value = item.split("=")
                    if value.startswith("${") and value.endswith("}"):
                        value = devel_environ.get(value[2:-1], value)
                    _environs[key] = value
                service["environment"] = [ "{}={}".format(k,v) for k,v in _environs.items() ]
        # updates current docker-compose (also versioned ... do not change by hand)
        with docker_compose_path.open('wt') as f:
            yaml.dump(content, f, default_flow_style=False)

    # TODO: comment when needed
    _recreate_compose_file()

    yield docker_compose_path

@pytest.fixture(scope='session')
def postgres_service(docker_services, docker_ip):
    """ Returns (host, port) to the director accessible from host """
    # No need to wait... webserver should do that
    return docker_ip, docker_services.port_for('postgres', 5432)

@pytest.fixture(scope='session')
def postgres_client(app_config):
    cfg = app_config["db"]["postgres"]
    url = DSN.format(**cfg)

    # NOTE: Comment this to avoid postgres_service
    # url = postgres_service

    # Configures db and initializes tables
    # Uses syncrounous engine for that
    engine = sa.create_engine(url, isolation_level="AUTOCOMMIT")
    metadata.create_all(bind=engine, tables=[users, confirmations], checkfirst=True)
    Base.metadata.create_all(engine)

    yield engine

    metadata.drop_all(engine)
    Base.metadata.drop_all(engine)
    engine.dispose()

@pytest.fixture(scope='session')
def rabbit_service(docker_services, docker_ip):
    """ Returns (host, port) to the director accessible from host """
    # No need to wait... webserver should do that
    return docker_ip, docker_services.port_for('rabbit', 15672)

@pytest.fixture(scope='session')
def minio_service(docker_services, docker_ip):
    """ Returns (host, port) to the director accessible from host """
    # No need to wait... webserver should do that
    return docker_ip, docker_services.port_for('minio', 9000)

@pytest.fixture(scope='session')
def director_service(docker_services, docker_ip):
    """ Returns (host, port) to the director accessible from host """
    # No need to wait... webserver should do that
    return docker_ip, docker_services.port_for('director', 8001)

@pytest.fixture(scope='session')
def storage_service(docker_services, docker_ip):
    """ Returns (host, port) to the director accessible from host """
    # No need to wait... webserver should do that
    return docker_ip, docker_services.port_for('storage', 8080)


@pytest.fixture(scope='session')
def apihub_service(docker_services, docker_ip):
    """ Returns (host, port) to the apihub accessible from host """
    # No need to wait... webserver/director should do that
    return docker_ip, docker_services.port_for('apihub', 8043)

# HELPERS ---------------------------------------------
def resolve_environ(service, environ):
    _environs = {}
    for item in service.get("environment", list()):
        key, value = item.split("=")
        if value.startswith("${") and value.endswith("}"):
            value = value[2:-1]
            if ":" in value:
                variable, default = value.split(":")
                value = environ.get(variable, default[1:])
            else:
                value = environ.get(value, value)   

        _environs[key] = value
    return _environs
