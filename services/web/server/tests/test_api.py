
# TODO: W0611:Unused import ...
# pylint: disable=W0611
# TODO: W0613:Unused argument ...
# pylint: disable=W0613
# W0621: Redefining name ... from outer scope
# pylint: disable=W0621
import logging
from pathlib import Path
import sys

import pytest
from aiohttp import web
import openapi_core
import yaml

from simcore_service_webserver import resources
from simcore_service_webserver.settings.constants import APP_OAS_KEY, API_URL_VERSION
import simcore_service_webserver.auth_routing as auth_routing

# TODO: reduce log from openapi_core loggers

@pytest.fixture
def here():
    return Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent

@pytest.fixture
def openapi_path(here):
    spec_path = here.parent / 'src/simcore_service_webserver/oas3/v0/openapi.yaml'
    return spec_path

@pytest.fixture
def spec_dict(openapi_path):
    with openapi_path.open() as f:
        spec_dict = yaml.safe_load(f)
    return spec_dict

#@pytest.fixture
#def client():


async def test_health_check(openapi_path, spec_dict, aiohttp_client, aiohttp_unused_port):
    app = web.Application()
    app[APP_OAS_KEY] = spec = openapi_core.create_spec(spec_dict, spec_url=openapi_path.as_uri())

    # fit specs server
    server_vars = spec.servers[0].variables
    host = server_vars['host'].default
    port = server_vars['port'].default = aiohttp_unused_port()

    routes = auth_routing.create(spec)
    app.router.add_routes(routes)

    client = await aiohttp_client(app, server_kwargs={'port': port, 'host': host})

    resp = await client.get("/v0/")
    assert resp.status == 200

    envelope = await resp.json()
    data, error = [envelope[k] for k in ('data', 'error')]

    assert data
    assert not error

    assert data['name'] == 'simcore-director-service'
    assert data['status'] == 'SERVICE_RUNNING'
