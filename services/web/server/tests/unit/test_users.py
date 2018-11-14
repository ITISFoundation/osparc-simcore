# pylint:disable=wildcard-import
# pylint:disable=unused-import
# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import pytest

from aiohttp import web

from servicelib.application_keys import APP_CONFIG_KEY
from simcore_service_webserver.rest import setup_rest, APP_OPENAPI_SPECS_KEY
from simcore_service_webserver.users import setup_users
from simcore_service_webserver.db import setup_db
from simcore_service_webserver.session import setup_session

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

    setup_db(app)
    setup_session(app)
    setup_rest(app, debug=True)
    setup_users(app)

    return loop.run_until_complete( aiohttp_client(app, server_kwargs=server_kwargs) )

@pytest.fixture
def response_validator(client):
    specs = client.app[APP_OPENAPI_SPECS_KEY]
    return specs


# Tests CRUD operations --------------------------------------------

# TODO: template for CRUD testing?

async def test_create(client):
    resp = await client.post("/%s" % RESOURCE_NAME, json={
        'service': "blackfynn",
        'token_key': '4k9lyzBTS',
        'token_secret': 'my secret'
    })
    payload = await resp.json()


async def test_read(client):
    # list all
    resp = await client.post("/%s" % RESOURCE_NAME)
    payload = await resp.json()

    # get one
    resp = await client.post("/%s/blackfynn" % RESOURCE_NAME)
    payload = await resp.json()


async def test_update(client):
    resp = await client.post("/%s/blackfynn" % RESOURCE_NAME, json={
        'token_key': '4k9lyzBTS',
        'token_secret': 'my secret'
    })
    payload = await resp.json()


async def test_delete(client):
    resp = await client.post("/%s/blackfynn" % RESOURCE_NAME)
    payload = await resp.json()
