""" Restful API

"""
import copy
import logging
import os
from collections import OrderedDict
from collections.abc import Sequence
from typing import Dict

from aiohttp import web

from servicelib import openapi
from servicelib.openapi import create_openapi_specs
from servicelib.rest_middlewares import append_rest_middlewares

from . import rest_routes
from .application_keys import APP_CONFIG_KEY
from .rest_settings import get_base_path

log = logging.getLogger(__name__)

# Settings ------------------------------------------
THIS_MODULE = __name__.split()[-1]
APP_OPENAPI_SPECS_KEY = "oas3"


#-------------------------------
def _get_server(servers, url):
    # Development server: http://{host}:{port}/{basePath}
    for server in servers:
        if server.url == url:
            return server
    raise ValueError("Cannot find server %s" % url)

def _setup_servers_specs(specs: openapi.Spec, app_config: Dict):
    # TODO: temporary solution. Move to servicelib. Modifying dynamically servers does not seem like
    # the best solution!

    if app_config.get('testing', True):
        # FIXME: host/port in host side!
        #  - server running inside container. use environ set by container to find port maps maps (see portainer)
        #  - server running in host

        devserver = _get_server(specs.servers, "http://{host}:{port}/{basePath}")
        if "IS_CONTAINER_CONTEXT" in os.environ:
            # TODO: fix. Retrieve mapped port!
            host,  port= 'localhost', 9081
        else:
            host, port = app_config['host'], app_config['port']

        devserver.variables['host'].default = host
        devserver.variables['port'].default = port

        HOSTNAMES = ('127.0.0.1', 'localhost')
        if host in HOSTNAMES:
            new_server = copy.deepcopy(devserver)
            new_server.variables['host'].default = HOSTNAMES[(HOSTNAMES.index(host)+1) % 2]
            specs.servers.append(new_server)

    # TODO: consider effect of reverse proxy
    public_url = app_config.get('public_url')
    if public_url:
        server = _get_server(specs.servers, "{publicUrl}/{basePath}")

        if isinstance(public_url, list): # FIXME: how to set environ as list
            server.variables['publicUrl'].default = public_url[0]
            if len(public_url)>1:
                for url in public_url[1:]:
                    new_server = copy.deepcopy(server)
                    new_server.variables['publicUrl'].default = url
                    specs.servers.append(new_server)
        else:
            server.variables['publicUrl'].default = public_url






def setup(app: web.Application):
    log.debug("Setting up %s ...", __name__)

    cfg = app[APP_CONFIG_KEY][THIS_MODULE]

    keep = {}


    # Load specs
    oas_cfg = cfg["openapi-specs"]
    if isinstance(oas_cfg, Sequence):

        oas_cfg = cfg[0]



    location = oas_cfg["location"]
    version  = oas_cfg["version"]

    specs = create_openapi_specs(location)




    keep[APP_OPENAPI_SPECS_KEY] = OrderedDict()
    keep[APP_OPENAPI_SPECS_KEY][version] = specs




    #app[THIS_MODULE_NAME] = keep




    try:
        openapi_path = cfg["openapi-specs"]["path"]
        specs = openapi.create_specs(openapi_path)

        # sets servers variables to current server's config
        app_config = app[APP_CONFIG_KEY]["main"] # TODO: define appconfig key based on config schema

        _setup_servers_specs(specs, app_config)

        # NOTE: after setup app-keys are all defined, but they might be set to None when they cannot
        # be initialized
        # TODO: What if many specs to expose? v0, v1, v2 ... perhaps a dict instead?
        # TODO: should freeze specs here??
        app[APP_OPENAPI_SPECS_KEY] = specs # validated openapi specs







        # setup rest submodules
        rest_routes.setup(app)

        base_path = get_base_path(specs)
        append_rest_middlewares(app, base_path)

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
