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
        app_config = app[APP_CONFIG_KEY]["app"] # TODO: define appconfig key based on config schema

        if app_config['testing']:
            # FIXME: host/port in host side!  Consider
            #  - server running inside container. use environ set by container to find port maps maps (see portainer)
            #  - server running in host
            DEVSERVER_INDEX = 0
            specs.servers[DEVSERVER_INDEX].variables['host'].default = 'localhost'
            specs.servers[DEVSERVER_INDEX].variables['port'].default = 9081

        # NOTE: after setup app-keys are all defined, but they might be set to None when they cannot
        # be initialized
        app[APP_OAS_KEY] = specs # validated openapi specs

        # collect here all maps and join in the router
        auth_routing.setup(app)

    except openapi.OpenAPIError:
        log.exception("Invalid rest API specs. Rest API is disabled!")
        specs = None



setup_rest = setup

__all__ = (
    'setup', 'setup_rest'
)
