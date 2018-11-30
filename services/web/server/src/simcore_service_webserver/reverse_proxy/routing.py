""" routing - rerouting to back-end dynamic services controled by the director

    - Director manages (spawns, monitor, ...) back-end dynamic services.
    - This sub-system communicates with the director via a client-sdk
    - Director client-sdk is created in another subsystem and available in the application at setup-time
    -

TODO: add validation, get/set app config
"""
import logging
from collections import OrderedDict
from typing import Callable, Dict, Tuple

import attr
from aiohttp import web

from .abc import ServiceResolutionPolicy
from .handlers.default import handler as default_handler
from .settings import PROXY_PATH_KEY, SERVICE_ID_KEY

logger = logging.getLogger(__name__)


@attr.s(auto_attribs=True)
class Wrapper:
    """ Wraps policy class to provide additional:
        - caches results
        - translate exceptions

    NOTE: wrapper.cache.clear()
    """
    encapsulated: ServiceResolutionPolicy
    cache: Dict[str, Tuple[str, str]] = OrderedDict()
    MAXSIZE = 128

    async def resolve(self, service_identifier: str) -> Tuple[str, str]:
        """ To reset cache, use cli.resolve_service.cache_reset()

        """
        if service_identifier in self.cache:
            return self.cache[service_identifier]

        try:
            # TODO: deal with timeouts?
            image_name = await self.encapsulated.get_image_name(service_identifier)
            service_url = await self.encapsulated.find_url(service_identifier)
            result = image_name, str(service_url)

            if len(self.cache) == 128:
                self.cache.popitem(False)
            self.cache[service_identifier] = result
            return result
        except Exception:
            logger.debug("Failed to resolve service", exc_info=True)
            # TODO: translate exception into HTTPStatus
            raise web.HTTPServiceUnavailable(
                reason="Cannot resolve service")


@attr.s(auto_attribs=True)
class ReverseChooser:
    resolver: Wrapper = attr.ib(converter=Wrapper)
    handlers: Dict = dict()

    def register_handler(self,
                         handler: Callable[..., web.StreamResponse], *,
                         image_name: str):
        self.handlers[image_name] = handler

    async def do_route(self, request: web.Request) -> web.Response:
        """ Resolves service and awaits

        """
        cli = self.resolver  # or self.resolver.encapsulated to remove caching

        service_identifier = request.match_info.get(SERVICE_ID_KEY)
        proxy_path = request.match_info.get(PROXY_PATH_KEY)
        mountpoint = request.path[:-len(proxy_path)].rstrip("/")

        image_name, service_url = await cli.resolve(service_identifier)  # pylint: disable=E1101

        # TODO: reset cache for given service_identifier when it is shutdown or reused
        # To clear cache, use cli.cache.clear()

        # raise web.HTTPServiceUnavailable()
        # TODO: director might be non-responding
        # TODO: service might be down

        # FIXME: add version as well
        handler = self.handlers.get(image_name, default_handler)


        response = await handler(request, service_url,
                                 mountpoint=mountpoint,
                                 proxy_path=proxy_path)
        return response
