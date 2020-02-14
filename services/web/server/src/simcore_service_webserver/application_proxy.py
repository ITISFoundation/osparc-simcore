""" Sets up reverse proxy in the application

    - app's reverse proxy dynamically reroutes communication between web-server's client
    and dynamic-backend services  (or dyb's)
    - couples director with reverse_proxy subsystems

 Use case
    - All requests to `/x/{serviceId}/{proxyPath}` are re-routed to a dyb service
    - dy-services are managed by the director service who monitors and controls its lifetime

"""
import logging
import os

import attr
from aiohttp import ClientSession, web
from yarl import URL

from servicelib.application_keys import APP_CLIENT_SESSION_KEY
from servicelib.application_setup import ModuleCategory, app_module_setup
from servicelib.rest_responses import unwrap_envelope

from .director.config import APP_DIRECTOR_API_KEY
from .reverse_proxy import setup_reverse_proxy
from .reverse_proxy.abc import ServiceResolutionPolicy

logger = logging.getLogger(__name__)

@attr.s(auto_attribs=True)
class ServiceMonitor(ServiceResolutionPolicy):
    app: web.Application
    base_url: URL

    @property
    def session(self) -> ClientSession:
        return self.app[APP_CLIENT_SESSION_KEY]

    async def _request_info(self, service_identifier: str):
        data = {}
        url = self.base_url / ("running_interactive_services/%s" % service_identifier)

        # TODO: see if client can cache consecutive calls. SEE self.cli.api_client.last_response is a
        # https://docs.aiohttp.org/en/stable/client_reference.html#response-object
        async with self.session.get(url, ssl=False) as resp:
            payload = await resp.json()
            data, error = unwrap_envelope(payload)
            if error:
                raise RuntimeError(str(error))
        return data

    # override
    async def get_image_name(self, service_identifier: str) -> str:
        data = await self._request_info(service_identifier)
        return data.get('service_key')


    # override
    async def find_url(self, service_identifier: str) -> URL:
        """ Returns the url = origin + mountpoint of the backend dynamic service identified

        """
        data = await self._request_info(service_identifier)
        base_url = URL.build(scheme="http",
                        host=data.get('service_host'),
                        port=data.get('service_port'),
                        path=data.get('service_basepath'))

        if not os.environ.get('IS_CONTAINER_CONTEXT'):
            # If server is not in swarm (e.g. during testing) then host:port = localhost:data['published_port']
            base_url = base_url.with_host('127.0.0.1') \
                               .with_port(data['published_port'])

        return base_url




@app_module_setup(__name__, ModuleCategory.ADDON,
    depends=["simcore_service_webserver.director", ],
    logger=logger)
def setup(app: web.Application):

    monitor = ServiceMonitor(app, base_url=app[APP_DIRECTOR_API_KEY])

    setup_reverse_proxy(app, monitor)
    assert "reverse_proxy" in app.router # nosec

    app["reverse_proxy.basemount"] = monitor.base_mountpoint


# alias
setup_app_proxy = setup


__all__ = (
    'setup_app_proxy'
)
