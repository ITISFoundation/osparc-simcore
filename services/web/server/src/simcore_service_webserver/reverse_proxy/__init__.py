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

from servicelib.application_setup import ModuleCategory, app_module_setup

from .abc import ServiceResolutionPolicy
from .handlers import jupyter, paraview
from .routing import ReverseChooser
from .settings import APP_SOCKETS_KEY, URL_PATH

logger = logging.getLogger(__name__)

MODULE_NAME = __name__.split(".")[-1]
ROUTE_NAME = MODULE_NAME
module_name = module_name = __name__.replace(".__init__", "")


async def _on_shutdown(app: web.Application):
    for ws in app[APP_SOCKETS_KEY]:
        await ws.close()


@app_module_setup(module_name, ModuleCategory.ADDON, logger=logger)
def setup(app: web.Application, service_resolver: ServiceResolutionPolicy):
    """Sets up reverse-proxy subsystem in the application (a la aiohttp)

    """
    chooser = ReverseChooser(resolver=service_resolver)

    # Registers reverse proxy handlers customized for specific service types
    for name in jupyter.SUPPORTED_IMAGE_NAME:
        chooser.register_handler(jupyter.handler, image_name=name)

    for name in paraview.SUPPORTED_IMAGE_NAME:
        chooser.register_handler(paraview.handler, image_name=name)

    # /x/{serviceId}/{proxyPath:.*}
    app.router.add_route(
        method="*", path=URL_PATH, handler=chooser.do_route, name=ROUTE_NAME
    )

    # chooser has same lifetime as the application
    app[__name__] = {"chooser": chooser}

    # cleans up all sockets created by the proxy
    app[APP_SOCKETS_KEY] = list()
    app.on_shutdown.append(_on_shutdown)


# alias
setup_reverse_proxy = setup

__all__ = "setup_reverse_proxy"
