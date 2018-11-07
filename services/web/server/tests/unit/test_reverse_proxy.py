# pylint:disable=wildcard-import
# pylint:disable=unused-import
# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import pytest
from aiohttp import web

from simcore_service_webserver.application_keys import APP_CONFIG_KEY
from simcore_service_webserver.reverse_proxy import setup_reverse_proxy

MOUNT_POINT = "/x/{}"


def create_backend_app(name, mount_point):
    async def handler(request: web.Request):
        """
            Echos back received info + its name
        """
        body = await request.text()
        return {
            "name": name,
            "received": {
                "method": request.method,
                "url": request.url,
                "body": body,
                "proxy_path": request.match("proxy_path")
            }
        }

    app = web.Application()
    app.router.add_route("*", mount_point + "/{proxy_path:.*}", handler)
    return app


async def spawn_backend_service(name, aiohttp_server):
    """ This emulates what the director will dynamically do"""

    app = create_proxied_app(name, mount_point=MOUNT_POINT.format(name))
    return await aiohttp_server(app)


# FIXTURES ------------------



@pytest.fixture
def reverse_proxy_server(loop, aiohttp_server, proxied_servers):
    """
        Application with reverse_proxy.setup
    """
    app = web.Application()

    app[APP_CONFIG_KEY] = {
        "reverse-proxy": {

        }
    }
    setup_reverse_proxy(app, debug=True)

    return loop.run_until_complete(aiohttp_server(app))


@pytest.fixture
def client(loop, aiohttp_client, reverse_proxy_server):
    return  loop.run_until_complete(aiohttp_client(reverse_proxy_server))


# TESTS ------------------------

def test_reverse_proxy(client):

    mount_point = MOUNT_POINT.format(sid="a")

    response = await client.get(mount_point + "/get-it")
    payload = await response.json()

    assert response.status == 200, payload

    response = await client.post(mount_point+ "/post-it", json={"to"="a"})
    payload = await response.json()

    assert response.status == 200, payload

    response = await client.put(mount_point+ "/put-it", json={"to"="a"})
    payload = await response.json()

    assert response.status == 200, payload
