""" Restful API

    - Loads and validates openapi specifications (oas)
    - Adds check and diagnostic routes
    - Activates middlewares

"""
import asyncio
import logging
#from copy import deepcopy

from aiohttp import web
from tenacity import before_sleep_log, retry, stop_after_attempt, wait_fixed

from servicelib import openapi
from servicelib.application_keys import APP_CONFIG_KEY
from servicelib.openapi import create_openapi_specs
from servicelib.rest_middlewares import append_rest_middlewares

from . import rest_routes
from .rest_config import APP_OPENAPI_SPECS_KEY, CONFIG_SECTION_NAME

log = logging.getLogger(__name__)


RETRY_WAIT_SECS = 2
RETRY_COUNT = 20
CONNECT_TIMEOUT_SECS = 30


def get_server(servers, url):
    # Development server: http://{host}:{port}/{basePath}
    for server in servers:
        if server.url == url:
            return server
    raise ValueError("Cannot find server %s in openapi specs" % url)


@retry( wait=wait_fixed(RETRY_WAIT_SECS),
        stop=stop_after_attempt(RETRY_COUNT),
        before_sleep=before_sleep_log(log, logging.INFO) )
async def get_specs(location):
    specs = await create_openapi_specs(location)
    return specs


def setup(app: web.Application, *, debug=False):
    log.debug("Setting up %s %s...", __name__, "[DEBUG]" if debug else "")

    # main_cfg = app[APP_CONFIG_KEY]["main"]
    cfg = app[APP_CONFIG_KEY][CONFIG_SECTION_NAME]

    try:
        #specs = await create_openapi_specs(location=cfg["location"])
        loop = asyncio.get_event_loop()
        location = cfg["location"]
        specs = loop.run_until_complete( get_specs(location) )

        # TODO: tmp removed but keep in case ...
        # sets servers variables to current server's config
        # extra_api_urls = cfg.get("extra_urls", list())
        # if debug:
        #     for host in {'127.0.0.1', 'localhost', main_cfg['host'] }:
        #         for port in {9081, main_cfg['port']}:
        #             extra_api_urls.append("http://{}:{}".format(host, port))

        # server = get_server(specs.servers, "{publicUrl}/{basePath}")
        # for url in extra_api_urls:
        #     new_server = deepcopy(server)
        #     new_server.variables['publicUrl'].default = url
        #     specs.servers.append(new_server)


        # TODO: What if many specs to expose? v0, v1, v2 ... perhaps a dict instead?
        # TODO: should freeze specs here??
        app[APP_OPENAPI_SPECS_KEY] = specs # validated openapi specs


        # diagnostics routes
        routes = rest_routes.create(specs)
        app.router.add_routes(routes)

        # middlewares
        base_path = openapi.get_base_path(specs)
        version  = cfg["version"]
        assert "/"+version == base_path, "Expected %s, got %s" %(version, base_path)
        append_rest_middlewares(app, base_path)

    except openapi.OpenAPIError:
        # TODO: protocol when some parts are unavailable because of failure
        # Define whether it is critical or this server can still
        # continue working offering partial services
        log.exception("Invalid rest API specs. Rest API is DISABLED")

# alias
setup_rest = setup

__all__ = (
    'setup_rest'
)
