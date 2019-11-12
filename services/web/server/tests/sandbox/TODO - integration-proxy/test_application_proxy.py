# pylint:disable=wildcard-import
# pylint:disable=unused-import
# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import asyncio

import pytest
import yaml
from aiohttp import web
from yarl import URL

import simcore_service_webserver.reverse_proxy.handlers.jupyter as rp_jupyter
import simcore_service_webserver.reverse_proxy.handlers.paraview as rp_paraview
from servicelib.application import create_safe_application
from servicelib.rest_responses import unwrap_envelope
from simcore_service_webserver.application import (setup_app_proxy,
                                                   setup_director, setup_rest)
from simcore_service_webserver.reverse_proxy.settings import PROXY_MOUNTPOINT

API_VERSION = 'v0'
@pytest.fixture
#def webserver_service(loop, app_config, director_service, aiohttp_unused_port, aiohttp_server, here):
#def webserver_service(loop, app_config, aiohttp_unused_port, aiohttp_server, here):
def webserver_service(docker_stack, loop, app_config, aiohttp_unused_port, aiohttp_server, here):
    # OVERRIDES app_config:
    #  - server lives with the testing framework
    port = app_config['main']['port'] = aiohttp_unused_port()
    host = app_config['main']['host'] = '127.0.0.1'

    #  - disable some subsystems
    app_config['rabbit']['enabled'] = False
    app_config['db']['enabled'] = False
    app_config['storage']['enabled'] = False

    # TODO: parse_and_validate
    config_app_path = here / "config.app.yaml"
    with (config_app_path).open('wt') as f:
        yaml.dump(app_config, f, default_flow_style=False)

    # app
    app = create_safe_application(app_config)

    setup_rest(app)
    setup_director(app, disable_login=True)
    setup_app_proxy(app) # <-----------|UNDER TEST

    server = loop.run_until_complete(aiohttp_server(app, port=port))

    yield server

    config_app_path.unlink()

@pytest.fixture
def client(loop, webserver_service,  aiohttp_client):
    """ webserver's API client

    """
    client = loop.run_until_complete(aiohttp_client(webserver_service) )
    return client


# TESTS ----------------------------------------------------------------------------
# + [(service_key, "????", "NJKfISIRB-%d"%i) for i, service_key in enumerate(rp_jupyter.SUPPORTED_IMAGE_NAME)]

@pytest.mark.parametrize("service_key,service_version,service_uuid", [
    (rp_jupyter.SUPPORTED_IMAGE_NAME[0], "1.7.0", "NJKfISIRB"),
    ("simcore/services/dynamic/raw-graphs", "2.8.0", "4J6GoxSNL"),
    ("simcore/services/dynamic/modeler/webserver", "2.7.0", "4k4zZL90S"),
    #(rp_paraview.SUPPORTED_IMAGE_NAME, "1.0.5", "EkE7LSU0r"),
    ])
async def test_reverse_proxy_workflow(client, service_key, service_version, service_uuid):
    """
        client <--> webserver <--> director

        - Tests interaction webserver<--->director
        - Tests webserserver.director subsystem
        - Tests webserserver.reverser proxy subsystem as well
    """
    # List services in registry ------------------------------------------------
    resp = await client.get("/"+API_VERSION+"/services?service_type=interactive")
    assert resp.status == 200, (await resp.text())

    payload = await resp.json()
    data, error = unwrap_envelope(payload)
    assert data
    assert not error

    assert any(srv['key']==service_key and srv['version']==service_version for srv in data), \
        "version of service NOT listed in registry"

    # Start backend dynamic service ------------------------------------------------
    resp = await client.post( URL("/"+API_VERSION+"/running_interactive_services").with_query(
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

    # Wait until service is responsive----------------------------------------------
    #TODO: all dynamic services boot time should be bounded!!
    WAIT_FIXED_SECS = 5
    MAX_TRIALS = 5

    count = 0
    while count<MAX_TRIALS:
        resp = await client.get("/"+API_VERSION+"/running_interactive_services/{}".format(service_uuid))
        # TODO: noticed some inconsistenciew between director's API and director's section of webserver API
        if resp.status==200:
            break
        await asyncio.sleep(WAIT_FIXED_SECS) # Does this make a difference being async??
        count +=1

    assert resp.status == 200, (await resp.text())

    # Talk with backend dynamic service ---------------------------------------------
    # TODO: webserver should not respond identical to the director!!
    service_basepath = PROXY_MOUNTPOINT + "/" + service_uuid

    resp = await client.get(service_basepath + '/')
    content = await resp.text()

    assert content
    assert resp.status == 200, content

    # Stop backend dynamic service ----------------------------------------------------
    resp = await client.delete("/"+API_VERSION+"/running_interactive_services/{}".format(service_uuid))
    assert resp.status == 204, (await resp.text())
