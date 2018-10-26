# W0621: Redefining name ... from outer scope
# pylint: disable=W0621

import pytest
from aiohttp import web

from simcore_service_webserver.application_keys import APP_CONFIG_KEY
from simcore_service_webserver.storage import setup_storage
from simcore_service_webserver.rest import setup_rest


@pytest.fixture
def client(loop, aiohttp_unused_port, aiohttp_client):
    app = web.Application()

    server_kwargs={'port': aiohttp_unused_port(), 'host': 'localhost'}

    app[APP_CONFIG_KEY] = { 'main': server_kwargs} # Fake config

    setup_rest(app)
    setup_storage(app)

    cli = loop.run_until_complete( aiohttp_client(app, server_kwargs=server_kwargs) )
    return cli

# FIXME: this requires auth
@pytest.mark.travis
async def test_locations(client):
    resp = await client.get("/v0/storage/locations")

    payload = await resp.json()
    assert resp.status == 200, str(payload)

    data, error = tuple( payload.get(k) for k in ('data', 'error') )

    assert len(data) == 1
    assert not error
