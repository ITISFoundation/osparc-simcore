# pylint:disable=wildcard-import
# pylint:disable=unused-import
# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import pytest
from aiohttp import web
import trafaret_config
import yaml

import simcore_service_webserver.reverse_proxy.handlers.jupyter as rp_jupyter
import simcore_service_webserver.reverse_proxy.handlers.paraview as rp_paraview
from servicelib.rest_responses import unwrap_envelope
from simcore_service_webserver.reverse_proxy.settings import PROXY_MOUNTPOINT
from simcore_service_webserver.application import setup_director, setup_app_proxy, APP_CONFIG_KEY, setup_rest
from simcore_service_webserver.application_config import app_schema
from simcore_service_webserver.resources import resources as app_resources

@pytest.fixture
def app_config(config_environ):
    # load from resources with this host_environ
    cfg_path = app_resources.get_path("config/server-docker-prod.yaml")

    # validates and fills all defaults/optional entries that normal load would not do
    cfg_dict = trafaret_config.read_and_validate(cfg_path, app_schema, vars=config_environ)

    return cfg_dict


@pytest.fixture
def webserver_service(loop, app_config, director_service, aiohttp_unused_port, aiohttp_server, here):
    # server lives with the testing framework
    port = app_config['main']['port'] = aiohttp_unused_port()
    host = '127.0.0.1'

    app_config['rabbit']['enabled'] = False

    for name in app_config:
        if name != "version":
            app_config[name]['host'] = host

    # For info dumps
    tmp_config = here / 'config.ignore.yaml'
    with tmp_config.open('wt') as f:
        yaml.dump(app_config, f, default_flow_style=False)

    # app
    app = web.Application()
    app[APP_CONFIG_KEY] = app_config

    setup_rest(app, debug=True)
    setup_director(app)
    setup_app_proxy(app) # <-----------

    server = loop.run_until_complete(aiohttp_server(app, port=port, host=host))
    return server

@pytest.fixture
def client(loop, webserver_service,  aiohttp_client):
    """ webserver's API client

    """
    client = loop.run_until_complete(aiohttp_client(webserver_service) )
    return client


# TESTS ----------------------------------------------------------------------------

@pytest.mark.parametrize("service_key,service_version,service_uuid", [
 (rp_jupyter.SUPPORTED_IMAGE_NAME, "1.6.0", "NJKfISIRB"),
 (rp_paraview.SUPPORTED_IMAGE_NAME, "1.0.5", "EkE7LSU0r"),
])
async def test_reverse_proxy_workflow(client, service_key, service_version, service_uuid):
    """
        client <--> webserver <--> director
    """
    import pdb; pdb.set_trace()

    # List services in registry
    resp = await client.get("/v0/services?service_type=interactive")
    assert resp.status == 200, (await resp.text())

    payload = await resp.json()
    data, error = unwrap_envelope(payload)
    assert data
    assert not error

    assert any(srv['key']==service_key and srv['version']==service_version for srv in data)

    # Start backend dynamic service
    service = {
        'service_key': service_key,
        'service_version': service_version,
        'service_uuid': service_uuid
    }
    resp = await client.post("/v0/running_interactive_services", json=service)
    assert resp.status == 200, (await resp.text())

    payload = await resp.json()
    data, error = unwrap_envelope(payload)
    assert data
    assert not error


    # Communicate with backend dynamic service
    # TODO: webserver should not respond identical to the director!!
    service_basepath = data['service_basepath']
    assert service_basepath.startswith(PROXY_MOUNTPOINT)

    resp = await client.get(service_basepath)
    assert resp.status == 200, (await resp.text())

    payload = await resp.json()
    data, error = unwrap_envelope(payload)
    assert data
    assert not error

    # Stop backend dynamic service
    resp = await client.delete("/v0/running_interactive_services/{service_uuid}".format(**service))
    assert resp.status == 204, (await resp.text())
