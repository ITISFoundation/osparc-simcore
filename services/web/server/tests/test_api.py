
# TODO: W0611:Unused import ...
# pylint: disable=W0611
# TODO: W0613:Unused argument ...
# pylint: disable=W0613
# W0621: Redefining name ... from outer scope
# pylint: disable=W0621
import logging
import sys
from pathlib import Path

import openapi_core
import pytest
import yaml
from aiohttp import web

from simcore_service_webserver import resources, rest
from simcore_service_webserver.settings.constants import (APP_CONFIG_KEY,
                                                          APP_OAS_KEY)

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

@pytest.fixture
def client(loop, aiohttp_unused_port, aiohttp_client):
    app = web.Application()

    server_kwargs={'port': aiohttp_unused_port(), 'host': 'localhost'}
    app[APP_CONFIG_KEY] = { 'app': server_kwargs } # Fake config
    rest.setup(app)

    cli = loop.run_until_complete( aiohttp_client(app, server_kwargs=server_kwargs) )
    return cli

async def test_health_check(client):
    resp = await client.get("/v0/")
    assert resp.status == 200

    envelope = await resp.json()
    data, error = [envelope[k] for k in ('data', 'error')]

    assert data
    assert not error

    assert data['name'] == 'simcore-director-service'
    assert data['status'] == 'SERVICE_RUNNING'

async def test_action_check(client):

    fake = {
        'path_value': 'one',
        'query_value': 'two',
        'body_value': {
            'a': 33,
            'b': 45
        }
    }

    resp = await client.post("/v0/check/echo", json=fake)
    assert resp.status == 200

    envelope = await resp.json()
    data, error = [envelope[k] for k in ('data', 'error')]

    assert data
    assert not error

    # TODO: validate response against specs

    assert data['path_value'] == 'echo'
    assert not data['query_value']
    #assert data['body_value'] == fake
