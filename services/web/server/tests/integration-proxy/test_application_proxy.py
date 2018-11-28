# pylint:disable=wildcard-import
# pylint:disable=unused-import
# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import pytest
import yaml
from aiohttp import web
from yarl import URL
import asyncio


import simcore_service_webserver.reverse_proxy.handlers.jupyter as rp_jupyter
import simcore_service_webserver.reverse_proxy.handlers.paraview as rp_paraview
from servicelib.rest_responses import unwrap_envelope
from simcore_service_webserver.application import (APP_CONFIG_KEY,
                                                   setup_app_proxy,
                                                   setup_director, setup_rest)
from simcore_service_webserver.reverse_proxy.settings import PROXY_MOUNTPOINT


@pytest.fixture
#def webserver_service(loop, app_config, director_service, aiohttp_unused_port, aiohttp_server, here):
def webserver_service(loop, app_config, aiohttp_unused_port, aiohttp_server, here):

    # OVERRIDES app_config:
    #  - server lives with the testing framework
    port = app_config['main']['port'] = aiohttp_unused_port()
    host = app_config['main']['host'] = '127.0.0.1'

    #  - disable some subsystems
    app_config['rabbit']['enabled'] = False
    app_config['db']['enabled'] = False
    app_config['storage']['enabled'] = False

    # TODO: parse_and_validate
    with (here / "config.app.yaml").open('wt') as f:
        yaml.dump(app_config, f, default_flow_style=False)

    # app
    app = web.Application()
    app[APP_CONFIG_KEY] = app_config

    setup_rest(app, debug=True)
    setup_director(app, disable_login=True)
    setup_app_proxy(app) # <-----------|

    server = loop.run_until_complete(aiohttp_server(app, port=port))
    return server

@pytest.fixture
def client(loop, webserver_service,  aiohttp_client):
    """ webserver's API client

    """
    client = loop.run_until_complete(aiohttp_client(webserver_service) )
    return client


# TESTS ----------------------------------------------------------------------------

@pytest.mark.parametrize("service_key,service_version,service_uuid", [
 (rp_jupyter.SUPPORTED_IMAGE_NAME, "1.7.0", "NJKfISIRB"),
 #(rp_paraview.SUPPORTED_IMAGE_NAME, "1.0.5", "EkE7LSU0r"),
])
async def test_reverse_proxy_workflow(client, service_key, service_version, service_uuid):
    """
        client <--> webserver <--> director
    """
    # List services in registry ----------------
    resp = await client.get("/v0/services?service_type=interactive")
    assert resp.status == 200, (await resp.text())

    payload = await resp.json()
    data, error = unwrap_envelope(payload)
    assert data
    assert not error

    assert any(srv['key']==service_key and srv['version']==service_version for srv in data)

    # Start backend dynamic service --------------
    resp = await client.post( URL("/v0/running_interactive_services").with_query(
         service_key=service_key,
         service_version =service_version,
         service_uuid = service_uuid)
    )
    assert resp.status == 201, (await resp.text())

    payload = await resp.json()
    data, error = unwrap_envelope(payload)
    assert data
    assert not error

    service_basepath = data['service_basepath']
    assert service_basepath == PROXY_MOUNTPOINT + "/" + service_uuid

    # TODO: wait until service is responsive!
    await asyncio.sleep(5)


    # Communicate with backend dynamic service --------------
    # TODO: webserver should not respond identical to the director!!
    service_basepath = PROXY_MOUNTPOINT + "/" + service_uuid

    resp = await client.get(service_basepath + '/')
    content = await resp.text()

    assert content
    assert resp.status == 200, content

    # Stop backend dynamic service
    resp = await client.delete("/v0/running_interactive_services/{}".format(service_uuid))
    assert resp.status == 204, (await resp.text())
