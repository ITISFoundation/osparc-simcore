""" routing - rerouting to back-end dynamic services controled by the director

    - Director manages (spawns, monitor, ...) back-end dynamic services.
    - This sub-system communicates with the director via a client-sdk
    - Director client-sdk is created in another subsystem and available in the application at setup-time
    -

TODO: add validation, get/set app config
"""
import logging
from functools import lru_cache
from typing import Callable, Dict, Tuple

import attr
from aiohttp import web

from .abc import ServiceResolutionPolicy
from .settings import PROXY_PATH_KEY, SERVICE_ID_KEY

logger = logging.getLogger(__name__)



@attr.s(auto_attribs=True)
class Wrapper:
    """ Wraps policy class to provide additional:
        - caching
        - treat exceptions

    """
    encapsulated: ServiceResolutionPolicy

    @lru_cache(maxsize=128)
    async def resolve(self, service_identifier) -> Tuple[str, str]:
        """ To reset cache, use cli.resolve_service.cache_reset()

        """
        try:
            # TODO: deal with timeouts?
            image_name = await self.encapsulated.get_image_name(service_identifier)
            service_url  = await self.encapsulated.get_url(service_identifier)
        except Exception: #pylint: disable=
            logger.debug("Failed to resolve service", exc_info=True)
            raise web.HTTPServiceUnavailable(reason="Cannot resolve service")

        return image_name, str(service_url)


@attr.s(auto_attribs=True)
class ReverseChooser:
    handlers: Dict=dict()
    resolver: Wrapper = attr.Factory(Wrapper)

    def register_handler(self,
                handler: Callable[[web.Request, str], web.Response], *,
                image_name: str):
        self.handlers[image_name] = handler

    async def do_route(self, request: web.Request) -> web.Response:
        """ Resolves service and awaits

        """
        cli = self.resolver # or self.resolver.encapsulated to remove caching

        service_identifier = request.path.match_info.get(SERVICE_ID_KEY)
        image_name, service_url = await cli.resolve(service_identifier)  #pylint: disable=E1101

        # TODO: reset cache for given service_identifier when it is shutdown or reused
        # To clear cache, use cli.resolve_service.cache_clear()


        # raise web.HTTPServiceUnavailable()
        # TODO: director might be non-responding
        # TODO: service might be down

        handler = self.handlers.get(image_name, None)
        if handler is not None:

            _proxy_path = request.path.match_info.get(PROXY_PATH_KEY)
            return (await handler(request, service_url))

        raise web.HTTPNotImplemented(reason="No handler implemented for this type of service")
