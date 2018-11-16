# pylint:disable=wildcard-import
# pylint:disable=unused-import
# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import collections

import pytest
from aiohttp import web
from yarl import URL

from servicelib.application_keys import APP_CONFIG_KEY
from servicelib.openapi_validation import validate_data
from simcore_service_webserver.db import setup_db
from simcore_service_webserver.rest import APP_OPENAPI_SPECS_KEY, setup_rest
from simcore_service_webserver.session import setup_session
from simcore_service_webserver.users import setup_users

API_VERSION = "v0"
RESOURCE_NAME = 'tokens'

@pytest.fixture
def client(loop, aiohttp_client, aiohttp_unused_port, api_specs_dir):
    app = web.Application()

    server_kwargs={'port': aiohttp_unused_port(), 'host': 'localhost'}
    # fake config
    app[APP_CONFIG_KEY] = {
        "main": server_kwargs,
        "rest": {
            "version": "v0",
            "location": str(api_specs_dir / API_VERSION / "openapi.yaml")
        }
    }

    # setup_db(app)
    setup_session(app)
    setup_rest(app, debug=True)
    setup_users(app)

    return loop.run_until_complete( aiohttp_client(app, server_kwargs=server_kwargs) )


# Tests CRUD operations --------------------------------------------
PREFIX = "/" + API_VERSION + "/my"


# TODO: template for CRUD testing?
# TODO: create parametrize fixture with resource_name
#


async def test_create(client):
    resp = await client.post(PREFIX + "/%s" % RESOURCE_NAME, json={
        'service': "blackfynn",
        'token_key': '4k9lyzBTS',
        'token_secret': 'my secret'
    })
    payload = await resp.json()
    assert resp.status == 201, payload


async def test_read(client):
    # get profile
    resp = await client.get(PREFIX)
    payload = await resp.json()
    assert resp.status == 200, payload

    # list all
    resp = await client.get(PREFIX + "/%s" % RESOURCE_NAME)
    payload = await resp.json()
    assert resp.status == 200, payload

    # get one
    resp = await client.get(PREFIX + "/%s/blackfynn" % RESOURCE_NAME)
    payload = await resp.json()
    assert resp.status == 200, payload


async def test_update(client):
    resp = await client.post(PREFIX + "/%s/blackfynn" % RESOURCE_NAME, json={
        'token_key': '4k9lyzBTS',
        'token_secret': 'my secret'
    })
    payload = await resp.json()
    assert resp.status == 200, payload


async def test_delete(client):
    resp = await client.post(PREFIX + "/%s/blackfynn" % RESOURCE_NAME)
    payload = await resp.json()

    assert resp.status == 204, payload
    assert not payload
