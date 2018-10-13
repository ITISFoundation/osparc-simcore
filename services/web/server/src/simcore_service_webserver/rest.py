import logging

from aiohttp import web

from simcore_servicelib import openapi

from . import auth_routing, resources
from .settings.constants import APP_CONFIG_KEY, APP_OAS_KEY, RSC_OPENAPI_KEY

log = logging.getLogger(__name__)

def setup(app: web.Application):
    log.debug("Setting up %s ...", __name__)

    # decide what specs to expose here
    openapi_path = resources.get_path(RSC_OPENAPI_KEY)

    try:
        specs = openapi.create_specs(openapi_path)

        # sets servers variables to current server's config
        app_config = app[APP_CONFIG_KEY]["app"]
        # FIXME: host/port in host side!
        host, port = 'localhost', 9081
        specs.servers[0].variables['host'].default = 'localhost'
        specs.servers[0].variables['port'].default = 9081
        #for server in specs.servers:
        #    for key in ('host', 'port'):
        #        if key in server.variables:
        #            server.variables[key].default = app_config[key]

    except openapi.OpenAPIError:
        log.exception("Invalid specs")
        specs = None

    # NOTE: after setup app-keys are all defined, but they might be set to None when they cannot
    # be initialized
    app[APP_OAS_KEY] = specs

    # collect here all maps and join in the router
    auth_routing.setup(app)

setup_rest = setup

__all__ = (
    'setup', 'setup_rest'
)
