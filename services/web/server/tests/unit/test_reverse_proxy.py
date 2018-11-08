# pylint:disable=wildcard-import
# pylint:disable=unused-import
# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import random
import string
from collections import defaultdict
from functools import lru_cache
from os.path import join
from typing import Any

import attr
import pytest
from aiohttp import web
from yarl import URL

from simcore_service_webserver.application_keys import APP_CONFIG_KEY
from simcore_service_webserver.reverse_proxy import setup_reverse_proxy
from simcore_service_webserver.reverse_proxy.abc import ServiceResolutionPolicy


def create_backend_app(name, image, basepath):
    async def handler(request: web.Request):
        """
            Echos back received info + its name
        """
        body = await request.text()
        return web.json_response({
            "name": name,
            "image": image,
            "received": {
                "method": request.method,
                "url": request.url,
                "body": body,
                "proxy_path": request.match("proxy_path")
            }
        })

    app = web.Application()
    app.router.add_route("*", basepath + "/{proxy_path:.*}", handler)
    return app

def random_name(lenght=5):
    return ''.join(random.choice([string.ascii_lowercase + string.digits for _ in range(lenght)]))

# FIXTURES ------------------

@pytest.fixture
def spawner_server(loop, aiohttp_server):
    """
        Spawns backend services  (emulates director)
    """
    # uses mountpoint as a unique identifier
    registry = {} # registry[mountpoint] -> {info:{}, server:}

    async def list_infos(reg: web.Request):
        return web.json_response([v["info"] for v in registry.values()])

    async def info(req: web.Request):
        serviceid = req.match_info.get("serviceId")

        for mountpoint, item in registry.items():
            if mountpoint.endswith(serviceid):
                return web.json_response( registry[mountpoint]["info"] )

        raise web.HTTPServiceUnavailable(
                reason="Service {} is not running".format(serviceid),
                content_type="application/json")

    async def start(req: web.Request):
        # client requests to run image in basepath
        data = await req.json()
        image = data["image"]
        basepath = data["basepath"] # corresponds to the PROXY_MOUNTPOINT
        serviceid = name = data.get("name", random_name()) # given or auto-generated here. Unique.
        # settings = data["settings"] image specific settings/config

        # determines unique mountpoint
        mountpoint = "{}/{}".format(basepath, serviceid)

        if mountpoint not in registry:
            server = await aiohttp_server(create_backend_app(name, image, mountpoint))
            registry[mountpoint] = {
                "server": server,
                "info":{
                    'name': name,
                    'image': image,
                    'mountpoint': mountpoint,
                    'id': serviceid,
                    'url': str( URL.build(
                            scheme=server.scheme,
                            host=server.host,
                            port=server.port,
                            path=mountpoint)  )
                }
            }

        # produces an identifier
        return web.json_response(registry[mountpoint]["info"])

    async def stop(req: web.Request):
        serviceid = req.match_info.get("serviceId")

        info = {}
        # determines unique mountpoint
        for mountpoint, item in registry.items():
            if mountpoint.endswith(serviceid):
                print("stopping %s ...", item["info"])
                service = registry[mountpoint]["server"]
                await service.close()
                info = registry.pop(mountpoint)["info"]
                break

        return web.json_response(info)


    app = web.Application()
    # API
    app.router.add_get( "/services", list_infos)
    app.router.add_get( "/services/{serviceId}", info)
    app.router.add_post("/services/start", start) # /services/?action=start
    app.router.add_get( "/services/{serviceId}/stop", stop) # servjces/?action=stop

    return loop.run_until_complete(aiohttp_server(app))


@pytest.fixture
def spawner_client(loop, aiohttp_client, spawner_server):
    return loop.run_until_complete(aiohttp_client(spawner_server))


@pytest.fixture
def reverse_proxy_server(loop, aiohttp_server, spawner_client):
    """
        Application with reverse_proxy.setup (emulates webserver)
    """

    @attr.s(auto_attribs=True)
    def ServiceMonitor(ServiceResolutionPolicy):
        client: Any=None

        # override
        async def get_image_name(self, service_identifier: str) -> str:
            res = await client.get("/services/%s" % service_identifier)
            info = await res.json()
            return info["image"]

        # override
        async def get_url(self, service_identifier: str) -> URL:
            res = await client.get("/services/%s" % service_identifier)
            info = await res.json()
            return info["mountpoint"]


    app = web.Application()

    # setup
    app["director.client"] = spawner_client
    monitor = ServiceMonitor(client=app["director.client"])

    # adds /x/ to router
    setup_reverse_proxy(app, monitor)
    app["reverse_proxy.basepath"] = monitor.service_basepath

    # adds api
    async def bypass(req: web.Request):
        method = req.method
        # /services/{serviceId}?action=xxx  -> /services/{serviceId}/{action}
        path = join(req.path, req.query.get("action", ""))
        body = None
        if method!="GET":
            body = await req.json()
            body["basepath"] = req.app["reverse_proxy.basepath"]

        cli = req.app["director.client"]
        res = await cli.request(method, path, json=body)
        return res

    # API:
    app.router.add_get("/services/{serviceId}", bypass)

    return loop.run_until_complete(aiohttp_server(app))


@pytest.fixture
def client(loop, aiohttp_client, reverse_proxy_server):
    return loop.run_until_complete(aiohttp_client(reverse_proxy_server))




# TESTS ------------------------


async def test_spawner(spawner_client):
    BASEPATH = "/x"

    resp = await spawner_client.get("/services")
    data = await resp.json()

    assert resp.status == 200, data
    assert data == []

    resp = await spawner_client.post("/services/start", json={
        "image": "A:latest",
        "name": "a",
        "basepath": BASEPATH
    })
    data = await resp.text()

    resp = await spawner_client.post("/services/start", json={
        "image": "B:latest",
        "name": "b",
        "basepath": BASEPATH
    })
    data = await resp.text()
    assert resp.status == 200, data

    resp = await spawner_client.get("/services")
    data = await resp.json()
    assert len(data) == 2
    assert resp.status == 200, data

    for sid in ( v["id"] for v in data ):
        resp = await spawner_client.get("/services/%s" % sid)
        txt = await resp.text()
        assert resp.status==200, txt
        data = await resp.json()

        resp = await spawner_client.get("/services/%s/stop" % sid)
        txt = await resp.text()
        assert resp.status==200, txt
        data = await resp.json()

    resp = await spawner_client.get("/services")
    data = await resp.json()
    assert len(data) == 0



#def test_reverse_proxy(client):
