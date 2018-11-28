
""" Tests reverse proxy within an environment having a
    - director service
    - apihub service
"""
# pylint:disable=wildcard-import
# pylint:disable=unused-import
# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import sys
from pathlib import Path
import os
import yaml
from copy import deepcopy

import pytest
from simcore_service_webserver.cli import create_environ

SERVICES = ['director', 'apihub']


@pytest.fixture(scope="session")
def here():
    return Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent


@pytest.fixture(scope='session')
def osparc_simcore_root_dir(here):
    root_dir = here.parent.parent.parent.parent.parent.resolve()
    assert root_dir.exists(), "Is this service within osparc-simcore repo?"
    assert any(root_dir.glob("services/web/server")), "%s not look like rootdir" % root_dir
    return root_dir


@pytest.fixture("session")
def env_devel_file(osparc_simcore_root_dir):
    env_devel_fpath = osparc_simcore_root_dir / ".env-devel"
    assert env_devel_fpath.exists()
    return env_devel_fpath


@pytest.fixture("session")
def services_docker_compose(osparc_simcore_root_dir):
    docker_compose_path = osparc_simcore_root_dir / "services" / "docker-compose.yml"
    assert docker_compose_path.exists()

    content = {}
    with docker_compose_path.open() as f:
        content = yaml.safe_load(f)
    return content


@pytest.fixture("session")
def devel_environ(env_devel_file):
    """ Environ dict from .env-devel """
    env_devel = {}
    with env_devel_file.open() as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                key, value = line.split("=")
                env_devel[key] = value
    return env_devel


@pytest.fixture(scope="session")
def webserver_environ(devel_environ, services_docker_compose):
    service = services_docker_compose['services']['webserver']
    environ = {'SIMCORE_WEB_OUTDIR': "not defined" } # THIS is defined docker image at build time!

    environ.update( resolve_environ(service, devel_environ) )
    return environ


@pytest.fixture(scope="session")
def config_environ(webserver_environ):
    """ Emulates environ in which webserver will run the config file

    """
    environ = {}
    environ.update(webserver_environ)
    environ.update( create_environ(skip_host_environ=True) )

    # ADD HERE OTHER OVERRIDES
    return environ


@pytest.fixture(scope='session')
def docker_compose_file(here, services_docker_compose, devel_environ):
    """ Overrides pytest-docker fixture

    """
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
    tmp_docker_compose = here / 'docker-compose.ignore.yml'
    with tmp_docker_compose.open('wt') as f:
        yaml.dump(content, f, default_flow_style=False)

    yield tmp_docker_compose


@pytest.fixture(scope='session')
def director_service(docker_services, docker_ip):
    """ Returns (host, port) to the director accessible from host """

    # No need to wait... webserver should do that

    return docker_ip, docker_services.port_for('director', 8001)

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
            value = environ.get(value[2:-1], value)
        _environs[key] = value
    return _environs
