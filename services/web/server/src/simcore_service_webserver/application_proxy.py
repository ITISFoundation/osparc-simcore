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
from aiohttp.client import ClientSession
from yarl import URL

from servicelib.rest_responses import unwrap_envelope

from .director.config import get_client_session
from .director.director_sdk import (ApiException, UsersApi,
                                    create_director_api_client)
from .reverse_proxy import setup_reverse_proxy
from .reverse_proxy.abc import ServiceResolutionPolicy

logger = logging.getLogger(__name__)


@attr.s(auto_attribs=True)
class ServiceMonitor(ServiceResolutionPolicy):
    cli: UsersApi=None
    session: ClientSession

    async def _request_info(self, service_identifier: str):
        data = {}
        # See API specs in api/specs/director/v0/openapi.yaml
        url = "v0/running_interactive_services/{}" % service_identifier

        # TODO: see if client can cache consecutive calls. SEE self.cli.api_client.last_response is a
        # https://docs.aiohttp.org/en/stable/client_reference.html#response-object
        async with self.session.get(url, ssl=False) as resp:
            payload = await resp.json()
            data, _error = unwrap_envelope(payload)

        return data

    async def _request_info_tmp(self, service_identifier: str):
        data = {}

        # GET /running_interactive_services/{service_uuid}
        #  200 -> RunningServiceEnveloped
        #  404 not found

        # TODO: see if client can cache consecutive calls. SEE self.cli.api_client.last_response is a
        # https://docs.aiohttp.org/en/stable/client_reference.html#response-object
        try:
            response, _status, _headers = await self.cli.running_interactive_services_get(service_uuid=service_identifier)

            payload = await response.json()
            data, _error = unwrap_envelope(payload)

        except ApiException:
            # FIXME: define error treatment policy!?
            logger.exception("Failed to request service info %s", service_identifier)
            data.clear()

        return data

    # override
    async def get_image_name(self, service_identifier: str) -> str:
        import pdb; pdb.set_trace()

        data = await self._request_info(service_identifier)
        #data.get('service_uuid')
        #data.get('service_basepath')
        #data.get('service_host')
        #data.get('service_port')
        #data.get('service_version')
        return data.get('service_key')


    # override
    async def find_url(self, service_identifier: str) -> URL:
        """ Returns the url = origin + mountpoint of the backend dynamic service identified

        """
        import pdb; pdb.set_trace()
        data = await self._request_info(service_identifier)
        return URL.build(scheme="http",
                         host=data.get('service_host'),
                         port=data.get('service_port'),
                         path=data.get('service_basepath', "/"))


def setup(app: web.Application):

    director_client = create_director_api_client(app)
    director_session = get_client_session(app)

    monitor = ServiceMonitor(director_client, director_session)
    setup_reverse_proxy(app, monitor)

    assert "reverse_proxy" in app.router
    app["reverse_proxy.basemount"] = monitor.base_mountpoint


# alias
setup_app_proxy = setup
