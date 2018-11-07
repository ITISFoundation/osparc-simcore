""" routing - rerouting to back-end dynamic services controled by the director

    - Director manages (spawns, monitor, ...) back-end dynamic services.
    - This sub-system communicates with the director via a client-sdk
    - Director client-sdk is created in another subsystem and available in the application at setup-time
    -

TODO: add validation, get/set app config
"""
from functools import lru_cache
from typing import Callable, Dict, Tuple

import attr
from aiohttp import web

from .abc import ServiceResolutionPolicy


@attr.s(auto_attribs=True)
class CachedResolver:
    """ Wraps client-sdk to cache some answers

    Reduces calls to external services
    """
    encapsulated: ServiceResolutionPolicy

    @lru_cache(maxsize=128)
    async def resolve(self, service_identifier) -> Tuple[str, str]:
        """ To reset cache, use cli.resolve_service.cache_reset()

        """
        image_name = await self.encapsulated.get_image_name(service_identifier)
        service_url  = await self.encapsulated.get_url(service_identifier)
        return image_name, str(service_url)


@attr.s(auto_attribs=True)
class ReverseChooser:
    handlers: Dict=dict()
    resolver: CachedResolver = attr.Factory(CachedResolver)
    # match_info keys --
    service_id_key: str
    proxy_path_key: str


    def register_handler(self, handler=Callable[web.Request, str], *, image_name:str):
        self.handlers[image_name] = handler

    async def do_route(self, request: web.Request):
        """ Resolves service and awaits

        """
        cli = self.resolver # or self.resolver.encapsulated to remove caching

        service_identifier = request.path.match_info.get(self.service_id_key)
        image_name, service_url = await cli.resolve(service_identifier)  #pylint: disable=E1101

        # TODO: reset cache for given service_identifier when it is shutdown or reused
        # To clear cache, use cli.resolve_service.cache_clear()


        # raise web.HTTPServiceUnavailable()
        # TODO: director might be non-responding
        # TODO: service might be down

        handler = self.handlers.get(image_name, None)
        if handler is not None:

            #proxy_path = request.path.match_info.get(self.proxy_path_key)
            return (await handler(request, service_url))

        raise web.HTTPNotImplemented(reason="No handler implemented for this type of service")
