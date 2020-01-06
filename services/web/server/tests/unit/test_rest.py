# pylint:disable=unused-import
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=no-name-in-module

import logging
import sys
from pathlib import Path

import openapi_core
import pytest
import yaml
from aiohttp import web

import simcore_service_webserver
from servicelib.application import create_safe_application
from servicelib.application_keys import APP_CONFIG_KEY, APP_OPENAPI_SPECS_KEY
from servicelib.rest_responses import unwrap_envelope
from simcore_service_webserver import resources, rest
from simcore_service_webserver.rest import setup_rest
from simcore_service_webserver.security import setup_security
from utils_assert import assert_status

logging.basicConfig(level=logging.INFO)


# TODO: reduce log from openapi_core loggers

@pytest.fixture
def openapi_path(api_specs_dir):
    specs_path = api_specs_dir / 'oas3/v0/openapi.yaml'
    assert specs_path.exits()
    return specs_path

@pytest.fixture
def spec_dict(openapi_path):
    with openapi_path.open() as f:
        spec_dict = yaml.safe_load(f)
    return spec_dict


@pytest.fixture
def client(loop, aiohttp_unused_port, aiohttp_client, api_specs_dir):
    app = create_safe_application()

    server_kwargs={'port': aiohttp_unused_port(), 'host': 'localhost'}
    # fake config
    app[APP_CONFIG_KEY] = {
        "main": server_kwargs,
        "rest": {
            "version": "v0",
            "location": str(api_specs_dir / "v0" / "openapi.yaml"),
            "enabled": True
        }
    }
    # activates only security+restAPI sub-modules
    setup_security(app)
    setup_rest(app)

    cli = loop.run_until_complete( aiohttp_client(app, server_kwargs=server_kwargs) )
    return cli

# ------------------------------------------

async def test_check_health(client):
    resp = await client.get("/v0/")
    payload = await resp.json()

    assert resp.status == 200, str(payload)
    data, error = tuple(payload.get(k) for k in ('data', 'error'))

    assert data
    assert not error

    assert data['name'] == 'simcore_service_webserver'
    assert data['status'] == 'SERVICE_RUNNING'

async def test_check_action(client):
    QUERY = 'value'
    ACTION = 'echo'
    FAKE = {
        'path_value': 'one',
        'query_value': 'two',
        'body_value': {
            'a': 'foo',
            'b': '45'
        }
    }

    resp = await client.post("/v0/check/{}?data={}".format(ACTION, QUERY), json=FAKE)
    payload = await resp.json()
    data, error = tuple(payload.get(k) for k in ('data', 'error'))

    assert resp.status == 200, str(payload)
    assert data
    assert not error

    # TODO: validate response against specs

    assert data['path_value'] == ACTION
    assert data['query_value'] == QUERY
    assert data['body_value'] == FAKE


async def test_frontend_config(client):
    url = client.app.router["get_config"].url_for()
    assert str(url) == "/v0/config"

    # default
    response = await client.get("/v0/config")

    data, _ = await assert_status(response, web.HTTPOk)
    assert not data["invitation_required"]

    # w/ invitation explicitly
    for enabled in (True, False):
        client.app[APP_CONFIG_KEY]['login'] = {'registration_invitation_required': enabled}
        response = await client.get("/v0/config")

        data, _ = await assert_status(response, web.HTTPOk)
        assert data["invitation_required"] is enabled
