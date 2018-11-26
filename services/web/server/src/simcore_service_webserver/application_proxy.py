from .reverse_proxy.abc import ServiceResolutionPolicy
from .reverse_proxy import setup_reverse_proxy

import attr
from aiohttp import web
from yarl import URL

@attr.s(auto_attribs=True)
class ServiceMonitor(ServiceResolutionPolicy):
    cli: TestClient = None

    # override
    async def get_image_name(self, service_identifier: str) -> str:
        res = await self.cli.get("/services/%s" % service_identifier)
        info = await res.json()
        return info["image"]

    # override
    async def find_url(self, service_identifier: str) -> URL:
        res = await self.cli.get("/services/%s" % service_identifier)
        info = await res.json()
        return info["url"]


def setup(app: web.Application):


    client = director_sdk.get_director()
    services = await director.services_get(service_type="interactive")

    monitor = ServiceMonitor(app["director.client"])

    setup_reverse_proxy(app, monitor)

    assert "reverse_proxy" in app.router

    app["reverse_proxy.basemount"] = monitor.base_mountpoint



# alias
setup_app_proxy = setup
