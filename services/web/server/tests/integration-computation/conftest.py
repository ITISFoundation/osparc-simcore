
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
import subprocess
import sys
from copy import deepcopy
from pathlib import Path
from typing import Dict

import docker
import pytest
import sqlalchemy as sa
import tenacity
import trafaret_config
import yaml
from sqlalchemy.orm import sessionmaker

from simcore_sdk.models.pipeline_models import Base
from simcore_service_webserver.application_config import app_schema
from simcore_service_webserver.cli import create_environ
from simcore_service_webserver.db import DSN
from simcore_service_webserver.db_models import confirmations, metadata, users
from simcore_service_webserver.resources import resources as app_resources

SERVICES = ['director', 'apihub', 'rabbit', 'postgres', 'sidecar', 'storage', 'minio']
TOOLS = ['adminer', 'flower', 'portainer']

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
def tools_docker_compose(osparc_simcore_root_dir) -> Dict[str, str]:
    docker_compose_path = osparc_simcore_root_dir / "services" / "docker-compose.tools.yml"
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
def docker_client():
    client = docker.from_env()
    yield client

@pytest.fixture(scope='session')
def docker_swarm(docker_client):
    docker_client.swarm.init()
    yield
    # teardown
    assert docker_client.swarm.leave(force=True) == True

def _recreate_compose_file(keep, services_compose, docker_compose_path, devel_environ):
    # reads service/docker-compose.yml
    content = deepcopy(services_compose)

    # remove unnecessary services    
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

@pytest.fixture(scope='session')
def docker_compose_file(here, services_docker_compose, devel_environ):
    """ Overrides pytest-docker fixture

    """
    docker_compose_path = here / 'docker-compose.yml'
    _recreate_compose_file(SERVICES, services_docker_compose, docker_compose_path, devel_environ)

    yield docker_compose_path

@pytest.fixture(scope='session')
def tools_docker_compose_file(here, tools_docker_compose, devel_environ):
    """ Overrides pytest-docker fixture

    """
    docker_compose_path = here / 'docker-compose.tools.yml'
    _recreate_compose_file(TOOLS, tools_docker_compose, docker_compose_path, devel_environ)

    yield docker_compose_path

@pytest.fixture(scope='session')
def postgres_db(app_config, webserver_environ, docker_stack):
    cfg = app_config["db"]["postgres"]
    url = DSN.format(**cfg)

    # NOTE: Comment this to avoid postgres_service
    wait_till_postgres_responsive(url)

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
def postgres_session(postgres_db):
    Session = sessionmaker(postgres_db)
    session = Session()
    yield session
    session.close()

@pytest.fixture(scope='session')
def docker_stack(docker_swarm, docker_client, docker_compose_file: Path, tools_docker_compose_file: Path):
    assert subprocess.run("docker-compose -f {} -f {} config > docker-compose.ignore.yml".format(docker_compose_file.name, tools_docker_compose_file.name), shell=True, cwd=docker_compose_file.parent).returncode == 0
    assert subprocess.run("docker stack deploy -c docker-compose.ignore.yml services", shell=True, cwd=docker_compose_file.parent).returncode == 0
    yield
    # clean up
    assert subprocess.run("docker stack rm services", shell=True).returncode == 0

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

@tenacity.retry(wait=tenacity.wait_fixed(0.1), stop=tenacity.stop_after_delay(30))
def wait_till_postgres_responsive(url):
    """Check if something responds to ``url`` """
    try:
        engine = sa.create_engine(url)
        conn = engine.connect()
        conn.close()
    except sa.exc.OperationalError:
        return False
    return True
