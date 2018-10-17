""" RESTful API for simcore_service_storage

"""
import copy
import logging
from typing import Dict

from aiohttp import web

from servicelib import openapi
from servicelib.rest_middlewares import envelope_middleware, error_middleware

from . import rest_routes
from .resources import resources
from .settings import APP_CONFIG_KEY, APP_OAS_KEY, RSC_OPENAPI_ROOTFILE_KEY

log = logging.getLogger(__name__)


def create_apispecs(app_config: Dict) -> openapi.Spec:

   # TODO: What if many specs to expose? v0, v1, v2 ...
    openapi_path = resources.get_path(RSC_OPENAPI_ROOTFILE_KEY)

    try:
        specs = openapi.create_specs(openapi_path)

        # sets servers variables to current server's config
        if app_config.get('testing', True):
            # FIXME: host/port in host side!  Consider
            #  - server running inside container. use environ set by container to find port maps maps (see portainer)
            #  - server running in host
            devserver = specs.servers[0]

            host, port = app_config['host'], app_config['port']

            devserver.variables['host'].default = host
            devserver.variables['port'].default = port

            HOSTNAMES = ('127.0.0.1', 'localhost')
            if host in HOSTNAMES:
                new_server = copy.deepcopy(devserver)
                new_server.variables['host'].default = HOSTNAMES[(HOSTNAMES.index(host)+1) % 2]
                specs.servers.append(new_server)

    except openapi.OpenAPIError:
        # TODO: protocol when some parts are unavailable because of failure
        # Define whether it is critical or this server can still
        # continue working offering partial services
        log.exception("Invalid rest API specs. Rest API is DISABLED")
        specs = None
    return specs

def setup(app: web.Application):
    """Setup the rest API module in the application in aiohttp fashion. """
    log.debug("Setting up %s ...", __name__)

    app_config = app[APP_CONFIG_KEY]['main'] # TODO: define appconfig key based on config schema

    api_specs = create_apispecs(app_config)

    if not api_specs:
        log.error("%s service disabled. Invalid specs", __name__)
        return

    # NOTE: after setup app-keys are all defined, but they might be set to None when they cannot
    # be initialized
    # TODO: What if many specs to expose? v0, v1, v2 ... perhaps a dict instead?
    # TODO: should freeze specs here??
    app[APP_OAS_KEY] = api_specs # validated openapi specs

    #Injects rest middlewares in the application
    app.middlewares.append(error_middleware)
    app.middlewares.append(envelope_middleware)

    rest_routes.setup(app)


# alias
setup_rest = setup

__all__ = (
    'setup_rest'
)
