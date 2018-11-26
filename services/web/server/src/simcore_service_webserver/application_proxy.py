""" Sets up reverse proxy in the application

    - app's reverse proxy dynamically reroutes communication between web-server's client
    and dynamic-backend services  (or dyb's)
    - couples director with reverse_proxy subsystems

 Use case
    - All requests to `/x/{serviceId}/{proxyPath}` are re-routed to a dyb service
    - dy-services are managed by the director service who monitors and controls its lifetime

"""
import logging

import attr
from aiohttp import web
from yarl import URL

from .director.director_sdk import (ApiException, UsersApi,
                                    create_director_api_client)
from .reverse_proxy import setup_reverse_proxy
from .reverse_proxy.abc import ServiceResolutionPolicy

logger = logging.getLogger(__name__)


@attr.s(auto_attribs=True)
class ServiceMonitor(ServiceResolutionPolicy):
    # See API specs in api/specs/director/v0/openapi.yaml
    cli: UsersApi

    # caches consecutive calls to same service_identifier
    info_service_id: str=None
    info_service_image: str=None
    info_service_url: str=None

    async def request_info(self, service_identifier: str):
        # GET /running_interactive_services/{service_uuid}
        #  200 -> RunningServiceEnveloped
        #  404 not found
        try:
            service = await self.cli.running_interactive_services_get(service_uuid=service_identifier)
        except ApiException:
            # FIXME: define error treatment policy!?
            logger.exception("Failed to request service info %s", str)

        self.info_service_id = service.service_uuid
        self.info_service_image = "{}:{}".format(service.service_key, service.service_version)

        # FIXME:Not sure format is correct!?
        self.info_service_url = service.entry_point + ":%d" % service.published_port \
                                + self.base_mountpoint + "/" + self.info_service_id

    # override
    async def get_image_name(self, service_identifier: str) -> str:
        if not self.info_service_image or self.info_service_id != service_identifier:
            await self.request_info(service_identifier)
        return self.info_service_image

    # override
    async def find_url(self, service_identifier: str) -> URL:
        if not self.info_service_url or self.info_service_id != service_identifier:
            await self.request_info(service_identifier)
        return self.info_service_url



def setup(app: web.Application):

    director = create_director_api_client(app)
    monitor = ServiceMonitor(director)
    setup_reverse_proxy(app, monitor)

    assert "reverse_proxy" in app.router
    app["reverse_proxy.basemount"] = monitor.base_mountpoint


# alias
setup_app_proxy = setup
