# pylint: disable=unused-argument
# pylint: disable=bare-except
# pylint:disable=redefined-outer-name

import logging
from typing import Dict

import pytest
import trafaret_config
import yaml
from aiohttp import web

from servicelib.application_keys import APP_CONFIG_KEY
from simcore_service_webserver.application_config import app_schema
from simcore_service_webserver.cli import create_environ
from simcore_service_webserver.db import setup_db
from simcore_service_webserver.resources import resources as app_resources
from simcore_service_webserver.rest import setup_rest

# imports the fixtures for the integration tests
pytest_plugins = [
    "fixtures.standard_directories",
    "fixtures.docker_compose",
    "fixtures.docker_swarm",
    "fixtures.docker_registry",
    "fixtures.celery_service",
    "fixtures.postgres_service"
]

log = logging.getLogger(__name__)
API_VERSION = "v0"

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
        environ['%s_HOST' % name.upper()] = '127.0.0.1'
        environ['%s_PORT' % name.upper()] = \
            services_docker_compose['services'][name]['ports'][0].split(':')[0] # takes port exposed
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
