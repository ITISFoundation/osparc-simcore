
""" Tests reverse proxy within an environment having a selection of
    core and tool services running in a swarm
"""
# pylint:disable=wildcard-import
# pylint:disable=unused-import
# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import logging
import os
import re
import subprocess
import sys
import time
from copy import deepcopy
from pathlib import Path
from typing import Dict

import docker
import pytest
import trafaret_config
import yaml

from simcore_service_webserver.application_config import app_schema
from simcore_service_webserver.cli import create_environ
from simcore_service_webserver.resources import resources as app_resources

logger = logging.getLogger(__name__)

# mute noisy loggers
logging.getLogger("openapi_spec_validator").setLevel(logging.WARNING)
logging.getLogger("sqlalchemy").setLevel(logging.WARNING)

# Maximum time expected for booting core services
MAX_BOOT_TIME_SECS = 20

# Selection of core and tool services started in this swarm fixture (integration)
core_services = [
    'director',
    ''
]

ops_services = [
    'adminer',
    'portainer'
]


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


def _load_docker_compose(docker_compose_path) -> Dict[str, str]:
    assert docker_compose_path.exists()
    content = {}
    with docker_compose_path.open() as f:
        content = yaml.safe_load(f)
    return content

@pytest.fixture("session")
def services_docker_compose(osparc_simcore_root_dir) -> Dict[str, str]:
    docker_compose_path = osparc_simcore_root_dir / "services" / "docker-compose.yml"
    return _load_docker_compose(docker_compose_path)

@pytest.fixture("session")
def ops_docker_compose(osparc_simcore_root_dir) -> Dict[str, str]:
    docker_compose_path = osparc_simcore_root_dir / "services" / "docker-compose-ops.yml"
    return _load_docker_compose(docker_compose_path)


@pytest.fixture("session")
def devel_environ(env_devel_file) -> Dict[str, str]:
    """ Environ dict from .env-devel """
    PATTERN_ENVIRON_EQUAL= re.compile(r"^(\w+)=(.*)$")
    env_devel = {}
    with env_devel_file.open() as f:
        for line in f:
            m = PATTERN_ENVIRON_EQUAL.match(line)
            if m:
                key, value = m.groups()
                env_devel[key] = str(value)
    # change some of the environ to accomodate the test case HERE
    #  ...
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
    for name in core_services:
        environ['%s_HOST' % name.upper()] = '127.0.0.1'
        environ['%s_PORT' % name.upper()] = \
            services_docker_compose['services'][name]['ports'][0].split(':')[
            0]  # takes port exposed
        # to swarm boundary since webserver is installed in the host and therefore outside the swarm's network
    from pprint import pprint
    pprint(environ)

    return environ


@pytest.fixture
def app_config(here, webserver_environ) -> Dict:
    config_file_path = here / "config.yaml"
    def _recreate_config_file():
        with app_resources.stream("config/server-docker-dev.yaml") as f:
            cfg = yaml.safe_load(f)
            # test webserver works in host
            cfg["main"]['host'] = '127.0.0.1'
            cfg["director"]["host"] = "127.0.0.1"

        with config_file_path.open('wt') as f:
            yaml.dump(cfg, f, default_flow_style=False)

    _recreate_config_file()

    logger.info(get_content_formatted(config_file_path))

    # Emulates cli
    config_environ = {}
    config_environ.update(webserver_environ)
    config_environ.update( create_environ(skip_host_environ=True) ) # TODO: can be done monkeypathcing os.environ and calling create_environ as well

    # validates
    cfg_dict = trafaret_config.read_and_validate(config_file_path, app_schema, vars=config_environ)

    yield cfg_dict

    # clean up
    # to debug configuration uncomment next line
    config_file_path.unlink()



# DOCKER STACK -------------------------------------------
@pytest.fixture(scope='session')
def docker_compose_file(here, services_docker_compose, devel_environ):
    """ Overrides pytest-docker fixture

    """
    docker_compose_path = here / 'docker-compose.yml'

    # creates a docker-compose file only with SERVICES and replaces environ
    _recreate_compose_file(core_services, services_docker_compose, docker_compose_path, devel_environ)

    logger.info(get_content_formatted(docker_compose_path))

    yield docker_compose_path

    # cleanup
    docker_compose_path.unlink()



@pytest.fixture(scope='session')
def docker_client():
    client = docker.from_env()
    yield client

@pytest.fixture(scope='session')
def docker_swarm(docker_client):
    docker_client.swarm.init()
    yield
    assert docker_client.swarm.leave(force=True) == True


@pytest.fixture(scope='session')
def docker_stack(docker_swarm, docker_client, docker_compose_file: Path):
    """

    """
    assert subprocess.run(
            "docker stack deploy -c {} services".format(docker_compose_file.name),
            shell=True,
            cwd=docker_compose_file.parent
        ).returncode == 0
    # NOTE:
    # ``failed to create service services_apihub: Error response from daemon: network services_default not found```
    # workaround is to restart daemon: ``sudo systemctl restart docker```

    time.sleep(MAX_BOOT_TIME_SECS)

    with docker_compose_file.open() as fp:
        docker_stack_cfg = yaml.safe_load(fp)

    yield docker_stack_cfg

    # clean up
    assert subprocess.run("docker stack rm services", shell=True).returncode == 0



# CORE SERVICES ---------------------------------------------
# @pytest.fixture(scope='session')
# def director_service(docker_services, docker_ip):
#     """ Returns (host, port) to the director accessible from host """

#     # No need to wait... webserver should do that

#     return docker_ip, docker_services.port_for('director', 8001)




# HELPERS ---------------------------------------------
# TODO: should be reused integration-*

def get_content_formatted(textfile: Path) -> str:
    return "{:=^10s}\n{}\n{:=^10s}".format(
            str(textfile),
            textfile.read_text("utf8"),
            '')

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


def _recreate_compose_file(keep, services_compose, docker_compose_path: Path, devel_environ):
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
