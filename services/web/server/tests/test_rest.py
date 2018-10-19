
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
from simcore_service_webserver.application_keys import (APP_CONFIG_KEY,
                                                          APP_OPENAPI_SPECS_KEY)
from simcore_service_webserver.security import setup_security
from simcore_service_webserver.rest import setup_rest

logging.basicConfig(level=logging.INFO)


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
    app[APP_CONFIG_KEY] = { "main": server_kwargs } # Fake config

    # activates only security+restAPI sub-modules
    setup_security(app)
    setup_rest(app)

    cli = loop.run_until_complete( aiohttp_client(app, server_kwargs=server_kwargs) )
    return cli




async def test_check_health(client):
    resp = await client.get("/v0/")
    assert resp.status == 200

    payload = await resp.json()
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



async def test_auth_register(client, caplog):
    caplog.set_level(logging.ERROR, logger='openapi_spec_validator')
    caplog.set_level(logging.ERROR, logger='openapi_core')

    response = await client.post('v0/auth/register',
        json = {
            'email': 'bar@mail.com',
            'password': 'my secret',
            'confirm': 'my secret',
            },
    )
    payload = await response.json()

    assert response.status==web.HTTPOk.status_code, str(payload)

    data, error = [payload[k] for k in ('data', 'error')]
    assert not error
    assert data

    assert 'message' in data
    assert data.get('logger') == "user"

    # possible usage
    client_log = logging.getLogger(data.get('logger', __name__))
    level = getattr(logging, data.get('level', "INFO"))
    client_log.log(level, msg=data['message'])

async def test_auth_login(client, caplog):

    log_filter = logging.Filter(name='simcore_service_webserver')
    logging.getLogger().addFilter(log_filter)

    # valid registration
    response = await client.post('v0/auth/register',
        json = {
            'email': 'foo@mymail.com',
            'password': 'my secret',
            'confirm': 'my secret',
            },
    )
    payload = await response.json()
    assert response.status==200, str(payload)

    data, error = unwrap_envelope(payload)
    assert not error
    assert data

    # FIXME: routing errors are returned as text and not json!!

    # valid login on registered ser
    response = await client.post('v0/auth/login',
        json = {
            'email': 'foo@mymail.com',
            'password': 'my secret',
            },
    )
    payload = await response.json()
    assert response.status==200, str(payload)

    data, error = unwrap_envelope(payload)
    assert not error
    assert data


    # invalid login
    response = await client.post('v0/auth/login',
        json = {
            'email': 'foo@mymail.com',
            'password': 'wrong pass',
            },
    )
    payload = await response.json()
    assert response.status==web.HTTPUnprocessableEntity.status_code, str(payload)

    data, error = unwrap_envelope(payload)
    assert error
    assert not data


  # logout
    response = await client.get('v0/auth/logout')

    payload = await response.json()
    assert response.status==web.HTTPOk.status_code, str(payload)

    data, error = unwrap_envelope(payload)
    assert not error
    assert data # logs
    assert all( k in data for k in ('level', 'logger', 'message') )



# utils

def unwrap_envelope(payload):
    return tuple( payload.get(k) for k in ('data', 'error') )
