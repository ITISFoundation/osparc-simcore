""" RESTful API for simcore_service_storage

"""
#import asyncio
import logging

import openapi_core
import yaml
from aiohttp import web

#from servicelib.client_session import get_client_session
#from servicelib.openapi import create_openapi_specs,
from servicelib.openapi import get_base_path
from servicelib.rest_middlewares import append_rest_middlewares

from . import rest_routes
from .resources import resources
#from .rest_config import CONFIG_SECTION_NAME
#from .settings import APP_CONFIG_KEY, API_VERSION_TAG, APP_OPENAPI_SPECS_KEY
from .settings import APP_OPENAPI_SPECS_KEY

#from yarl import URL

#from .utils import assert_enpoint_is_ok, is_url

log = logging.getLogger(__name__)


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

    #cfg = app[APP_CONFIG_KEY][CONFIG_SECTION_NAME]
    #location = "{}/storage/{}/openapi.yaml".format(cfg["oas_repo"], API_VERSION_TAG)

    # TODO: refactor this and into something more maintainable
    #loop = asyncio.get_event_loop()
    #session = get_client_session(app)
    #if is_url(location):
    #    loop.run_until_complete( assert_enpoint_is_ok(session, URL(location)) )
    #api_specs = loop.run_until_complete( create_openapi_specs(location, session) )

    spec_path = resources.get_path('api/openapi.yaml')
    with spec_path.open() as fh:
        spec_dict = yaml.safe_load(fh)
    api_specs = openapi_core.create_spec(spec_dict, spec_path.as_uri())

    # validated openapi specs
    app[APP_OPENAPI_SPECS_KEY] = api_specs

    # Connects handlers
    routes = rest_routes.create(api_specs)
    app.router.add_routes(routes)

    log.debug("routes:\n\t%s", "\n\t".join(map(str, routes)) )

    # Enable error, validation and envelop middleware on API routes
    base_path = get_base_path(api_specs)
    append_rest_middlewares(app, base_path)


# alias
setup_rest = setup

__all__ = (
    'setup_rest'
)
