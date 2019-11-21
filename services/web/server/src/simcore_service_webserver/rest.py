""" Restful API

    - Loads and validates openapi specifications (oas)
    - Adds check and diagnostic routes
    - Activates middlewares

"""
#import asyncio
import logging

import openapi_core
import yaml
from aiohttp import web
from tenacity import before_sleep_log, retry, stop_after_attempt, wait_fixed

from servicelib import openapi
from servicelib.application_keys import APP_CONFIG_KEY
from servicelib.application_setup import ModuleCategory, app_module_setup
from servicelib.client_session import get_client_session
from servicelib.openapi import create_openapi_specs
from servicelib.rest_middlewares import append_rest_middlewares
from simcore_service_webserver.resources import resources

from . import rest_routes
from .rest_config import APP_OPENAPI_SPECS_KEY, CONFIG_SECTION_NAME

log = logging.getLogger(__name__)


RETRY_WAIT_SECS = 2
RETRY_COUNT = 20
CONNECT_TIMEOUT_SECS = 30


@retry( wait=wait_fixed(RETRY_WAIT_SECS),
        stop=stop_after_attempt(RETRY_COUNT),
        before_sleep=before_sleep_log(log, logging.INFO) )
async def get_specs(app, location):
    session = get_client_session(app)
    specs = await create_openapi_specs(location, session)
    return specs


@app_module_setup(__name__, ModuleCategory.ADDON,
    depends=['simcore_service_webserver.security'],
    logger=log)
def setup(app: web.Application):
    cfg = app[APP_CONFIG_KEY][CONFIG_SECTION_NAME]

    try:
        #loop = asyncio.get_event_loop()
        #location = cfg["location"]
        #specs = loop.run_until_complete( get_specs(app, location) )
        # FIXME: remove location from config
        # FIXME: openapi_core has a bug and cannot support additionalProperties: false/true
        spec_path = resources.get_path('api/openapi.yaml')
        with spec_path.open() as fh:
            spec_dict = yaml.safe_load(fh)
        specs = openapi_core.create_spec(spec_dict, spec_path.as_uri())

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
