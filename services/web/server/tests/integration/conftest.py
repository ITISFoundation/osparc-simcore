# pylint: disable=unused-argument
# pylint: disable=bare-except
# pylint:disable=redefined-outer-name

import logging
import sys
from pathlib import Path
from typing import Dict

import docker
import pytest
import trafaret_config
import yaml
from simcore_service_webserver.application_config import app_schema
from simcore_service_webserver.cli import create_environ
from simcore_service_webserver.resources import resources as app_resources

# imports the fixtures for the integration tests
pytest_plugins = [
    "fixtures.standard_directories",
    "fixtures.docker_compose",
    "fixtures.docker_swarm",
    "fixtures.docker_registry",
    "fixtures.rabbit_service",
    "fixtures.celery_service",
    "fixtures.postgres_service"
]

log = logging.getLogger(__name__)

sys.path.append(str(Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent.parent / 'helpers'))

API_VERSION = "v0"


@pytest.fixture(scope='session')
def here():
    return Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent

@pytest.fixture(scope="module")
def webserver_environ(request, devel_environ, services_docker_compose) -> Dict[str, str]:
    """ Environment variables for the webserver application

    """
    dockerfile_environ = {'SIMCORE_WEB_OUTDIR': "undefined" } # TODO: parse webserver dockerfile ??

    service = services_docker_compose['services']['webserver']
    docker_compose_environ = resolve_environ(service, devel_environ)

    environ = {}
    environ.update(dockerfile_environ)
    environ.update(docker_compose_environ)

    # get the list of core services the test module wants
    core_services = getattr(request.module, 'core_services', [])
    # OVERRIDES:
    #   One of the biggest differences with respect to the real system
    #   is that the webserver application is replaced by a light-weight
    #   version tha loads only the subsystems under test. For that reason,
    #   the test webserver is built-up in webserver_service fixture that runs
    #   on the host.
    for name in core_services:
        if 'ports' not in services_docker_compose['services'][name]:
            continue
        
        # published port is sometimes dynamically defined by the swarm

        environ['%s_HOST' % name.upper()] = '127.0.0.1'
        environ['%s_PORT' % name.upper()] = get_service_published_port(name)
        # to swarm boundary since webserver is installed in the host and therefore outside the swarm's network
    from pprint import pprint
    pprint(environ)
    return environ

@pytest.fixture(scope='module')
def app_config(here, webserver_environ) -> Dict:
    config_file_path = here / "config.yaml"
    def _recreate_config_file():
        with app_resources.stream("config/server-docker-dev.yaml") as f:
            cfg = yaml.safe_load(f)
            # test webserver works in host
            cfg["main"]['host'] = '127.0.0.1'

        with config_file_path.open('wt') as f:
            yaml.dump(cfg, f, default_flow_style=False)

    _recreate_config_file()

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

## HELPERS
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

def get_service_published_port(service_name: str) -> str:
    published_port = "none"
    client = docker.from_env()
    services = [x for x in client.services.list() if service_name in x.name]
    if not services:
        return published_port
    service_endpoint = services[0].attrs["Endpoint"]
    
    if "Ports" not in service_endpoint or not service_endpoint["Ports"]:
        return published_port
    
    published_port = service_endpoint["Ports"][0]["PublishedPort"]
    return str(published_port)