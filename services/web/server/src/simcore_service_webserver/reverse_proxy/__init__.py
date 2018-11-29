""" reverse proxy subsystem

    Dynamically reroutes communication between web-server client and dynamic-backend services  (or dyb's)

    - All requests to `/x/{serviceId}/{proxyPath}` are resolved and rerouted to a dyb service
    - dyb services live in the backend
    - dyb services are identifiable (have an id)
    - dyb services are accessible (have a URL-endpoint) from the web-server.
    - Customized reverse proxy handlers for dy-jupyter, dy-modeling and dy-3dvis

"""
import logging

from aiohttp import web

from .abc import ServiceResolutionPolicy
from .routing import ReverseChooser
from .handlers import jupyter, paraview
from .settings import URL_PATH

logger = logging.getLogger(__name__)

MODULE_NAME = __name__.split(".")[-1]
ROUTE_NAME = MODULE_NAME


def setup(app: web.Application, service_resolver: ServiceResolutionPolicy):
    """Sets up reverse-proxy subsystem in the application (a la aiohttp)

    """
    logger.debug("Setting up %s ...", __name__)

    chooser = ReverseChooser(resolver=service_resolver)

    # Registers reverse proxy handlers customized for specific service types
    chooser.register_handler(jupyter.handler,
                             image_name=jupyter.SUPPORTED_IMAGE_NAME)

    chooser.register_handler(paraview.handler,
                             image_name=paraview.SUPPORTED_IMAGE_NAME)

    # /x/{serviceId}/{proxyPath:.*}
    app.router.add_route(method='*', path=URL_PATH,
                         handler=chooser.do_route, name=ROUTE_NAME)

    # chooser has same lifetime as the application
    app[__name__] = {"chooser": chooser}


# alias
setup_reverse_proxy = setup

__all__ = (
    'setup_reverse_proxy'
)
