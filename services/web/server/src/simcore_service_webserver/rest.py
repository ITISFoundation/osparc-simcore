""" Restful API

"""
import copy
import logging
import os

from aiohttp import web

from servicelib import openapi
from servicelib.rest_middlewares import envelope_middleware, error_middleware

from . import rest_routes
from .application_keys import APP_CONFIG_KEY, APP_OPENAPI_SPECS_KEY
from .resources import resources
from .resources_keys import RSC_OPENAPI_ROOTFILE_KEY

log = logging.getLogger(__name__)


def setup(app: web.Application):
    log.debug("Setting up %s ...", __name__)

    # TODO: What if many specs to expose? v0, v1, v2 ...
    openapi_path = resources.get_path(RSC_OPENAPI_ROOTFILE_KEY)

    try:
        specs = openapi.create_specs(openapi_path)

        # sets servers variables to current server's config
        app_config = app[APP_CONFIG_KEY]["main"] # TODO: define appconfig key based on config schema

        if app_config.get('testing', True):
            # FIXME: host/port in host side!  Consider
            #  - server running inside container. use environ set by container to find port maps maps (see portainer)
            #  - server running in host
            in_container = "IS_CONTAINER_CONTEXT" in os.environ
            devserver = specs.servers[0]

            host, port = app_config['host'], app_config['port']

            devserver.variables['host'].default = host
            devserver.variables['port'].default = 9081 if in_container else port  # TODO: fix. Retrieve mapped port!

            HOSTNAMES = ('127.0.0.1', 'localhost')
            if host in HOSTNAMES:
                new_server = copy.deepcopy(devserver)
                new_server.variables['host'].default = HOSTNAMES[(HOSTNAMES.index(host)+1) % 2]
                specs.servers.append(new_server)

        # TODO: consider case of many public_url and effect of reverse proxy
        if 'public_url' in app_config:  # Corresponds to ${OSPARC_PUBLIC_URL}
            for server in specs.servers:
                if 'public_url' in server.variables:
                    server.variables['public_url'].default = app_config['public_url']


        # NOTE: after setup app-keys are all defined, but they might be set to None when they cannot
        # be initialized
        # TODO: What if many specs to expose? v0, v1, v2 ... perhaps a dict instead?
        # TODO: should freeze specs here??
        app[APP_OPENAPI_SPECS_KEY] = specs # validated openapi specs

        # setup rest submodules
        rest_routes.setup(app)

        app.middlewares.append(error_middleware)
        app.middlewares.append(envelope_middleware)

    except openapi.OpenAPIError:
        # TODO: protocol when some parts are unavailable because of failure
        # Define whether it is critical or this server can still
        # continue working offering partial services
        log.exception("Invalid rest API specs. Rest API is DISABLED")
        specs = None

# alias
setup_rest = setup

__all__ = (
    'setup', 'setup_rest'
)
