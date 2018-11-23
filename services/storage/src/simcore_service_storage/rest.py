""" RESTful API for simcore_service_storage

"""
import asyncio
import copy
import logging
from pprint import pformat
from typing import Dict

from aiohttp import web

from servicelib import openapi
from servicelib.openapi import create_openapi_specs, get_base_path
from servicelib.rest_middlewares import append_rest_middlewares

from . import rest_routes
from .rest_config import CONFIG_SECTION_NAME
from .settings import API_VERSION_TAG, APP_CONFIG_KEY, APP_OPENAPI_SPECS_KEY

log = logging.getLogger(__name__)



#TODO: move to servicelib
def _get_server(servers, url):
    # Development server: http://{host}:{port}/{basePath}
    for server in servers:
        if server.url == url:
            return server
    raise ValueError("Cannot find server %s" % url)

def _setup_servers_specs(specs: openapi.Spec, app_config: Dict) -> openapi.Spec:
    # TODO: temporary solution. Move to servicelib. Modifying dynamically servers does not seem like
    # the best solution!

    if app_config.get('testing', True):
        # FIXME: host/port in host side!
        #  - server running inside container. use environ set by container to find port maps maps (see portainer)
        #  - server running in host

        devserver = _get_server(specs.servers, "http://{host}:{port}/{basePath}")
        host, port = app_config['host'], app_config['port']

        devserver.variables['host'].default = host
        devserver.variables['port'].default = port

        # Extends server specs to locahosts
        for host in {'127.0.0.1', 'localhost', host}:
            for port in {port, 11111, 8080}:
                log.info("Extending to server %s:%s", host, port)
                new_server = copy.deepcopy(devserver)
                new_server.variables['host'].default = host
                new_server.variables['port'].default = port
                specs.servers.append(new_server)

        for s in specs.servers:
            if 'host' in s.variables.keys():
                log.info("SERVER SPEC %s:%s", s.variables['host'].default, s.variables['port'].default)
            else:
                log.info("SERVER SPEC storage :%s", s.variables['port'].default)


    return specs


# def create_apispecs(app_config: Dict) -> openapi.Spec:
#    # TODO: What if many specs to expose? v0, v1, v2 ...
#     openapi_path = resources.get_path(RSC_OPENAPI_ROOTFILE_KEY)

#     try:
#         specs = openapi.create_specs(openapi_path)
#         specs = _setup_servers_specs(specs, app_config)

#     except openapi.OpenAPIError:
#         # TODO: protocol when some parts are unavailable because of failure
#         # Define whether it is critical or this server can still
#         # continue working offering partial services
#         log.exception("Invalid rest API specs. Rest API is DISABLED")
#         specs = None
#     return specs


def setup(app: web.Application):
    """Setup the rest API module in the application in aiohttp fashion.

        - users "rest" section of configuration (see schema in rest_config.py)
        - loads and validate openapi specs from a remote (e.g. apihub) or local location
        - connects openapi specs paths to handlers (see rest_routes.py)
        - enables error, validation and envelope middlewares on API routes


        IMPORTANT: this is a critical subsystem. Any failure should stop
        the system startup. It CANNOT be simply disabled & continue
    """
    log.debug("Setting up %s ...", __name__)

    cfg = app[APP_CONFIG_KEY][CONFIG_SECTION_NAME]

    # app_config = app[APP_CONFIG_KEY]['main'] # TODO: define appconfig key based on config schema
    # api_specs = create_apispecs(app_config)

    loop = asyncio.get_event_loop()
    location = "{}/storage/{}/openapi.yaml".format(cfg["oas_repo"], API_VERSION_TAG)
    api_specs = loop.run_until_complete( create_openapi_specs(location) )

    # validated openapi specs
    app[APP_OPENAPI_SPECS_KEY] = api_specs

    # Connects handlers
    routes = rest_routes.create(api_specs)
    app.router.add_routes(routes)

    log.debug("routes: %s", pformat(routes))

    # Enable error, validation and envelop middleware on API routes
    base_path = get_base_path(api_specs)
    append_rest_middlewares(app, base_path)


# alias
setup_rest = setup

__all__ = (
    'setup_rest'
)
