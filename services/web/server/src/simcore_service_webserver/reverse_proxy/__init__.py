""" reverse proxy subsystem

    Dynamically reroutes communication between web-server client and dynamic-backend services  (or dyb's)

 Use case
    - All requests to `/x/{serviceId}/{proxyPath}` are re-routed to resolved dyb service
    - dy-services are managed by the director service who monitors and controls its lifetime
    - a client-sdk to query the director is passed upon setup
    - Customized reverse proxy handlers for dy-jupyter, dy-modeling and dy-3dvis

"""
import logging

from aiohttp import web


from .abc import ServiceResolutionPolicy
from .routing import ReverseChooser
from .handlers import jupyter, paraview
from .settings import URL_PATH

logger = logging.getLogger(__name__)



def setup(app: web.Application, service_resolver: ServiceResolutionPolicy):
    """Sets up reverse-proxy subsystem in the application (a la aiohttp)

    """
    logger.debug("Setting up %s ...", __name__)

    chooser = ReverseChooser(resolver=service_resolver)

    # Registers reverse proxy handlers per service type.
    chooser.register_handler(jupyter.handler,
        image_name=jupyter.SUPPORTED_IMAGE_NAME)

    chooser.register_handler(paraview.handler,
        image_name=paraview.SUPPORTED_IMAGE_NAME)

    # TODO: add default handler in test mode?

    # URL_PATH looks like:  /x/{serviceId}/{proxyPath:.*}
    app.router.add_routes('*', URL_PATH,  chooser.do_route)

    # chooser has same lifetime as application
    app[__name__] = {"chooser": chooser}



# alias
setup_reverse_proxy = setup

__all__ = (
    'setup_reverse_proxy'
)
