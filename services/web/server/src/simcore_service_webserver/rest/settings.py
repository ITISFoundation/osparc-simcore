import logging
from pathlib import Path

from aiohttp import hdrs
import yaml

from ._generated_code.models.base_model_ import Model
from .middlewares import (
    Jsonify, jsonify,
    handle_errors
)
from .. import resources
from ..comp_backend_api import comp_backend_routes
from ..registry_api import registry_routes

_LOGGER = logging.getLogger(__name__)

#-------------------------------------------------------------------
# NOTE: Set here the version of API to be used
# NOTE: Versions and name consistency tested in test_rest.py
API_MAJOR_VERSION = 1
API_URL_PREFIX = "v{:.0f}".format(API_MAJOR_VERSION)
API_SPECS_NAME = ".oas3/{}/openapi.yaml".format(API_URL_PREFIX)
#-------------------------------------------------------------------

def api_version() -> str:
    specs = yaml.load(resources.stream(API_SPECS_NAME))
    return specs['info']['version']

def api_specification_path() -> Path:
    return resources.get_path(API_SPECS_NAME)

def setup_rest(app):
    """Setup the rest API module in the application in aiohttp fashion. """
    _LOGGER.debug("Setting up %s ...", __name__)

    router = app.router

    router.set_cors(app, domains='*', headers=(
        (hdrs.ACCESS_CONTROL_EXPOSE_HEADERS, hdrs.AUTHORIZATION),
    ))

    # add automatic jsonification of the models located in generated code
    jsonify.singleton = Jsonify(indent=3, ensure_ascii=False)
    jsonify.singleton.add_converter(Model, lambda o: o.to_dict(), score=0)

    app.middlewares.append(jsonify)
    app.middlewares.append(handle_errors)


    # FIXME: create a router in scsdk that extends SwaggerRouter
    def _add_routes(self, routes):
        """Append routes to route table.

        Parameter should be a sequence of RouteDef objects.
        """
        for route_obj in routes:
            route_obj.register(self)

    # NOTE: Keep a single digit version in the url
    #prefix = "/api/v{:.0f}".format(float(__version__))

    #router.add_post(prefix+"/login", login, name="login")
    #router.add_get(prefix+"/logout", logout, name="logout")
    #router.add_get(prefix+"/ping", ping, name="ping")

    # TODO: add authorization on there routes

    #app.router.add_routes(registry_routes)
    #app.router.add_routes(comp_backend_routes)
    _add_routes(router, registry_routes)
    _add_routes(router, comp_backend_routes)

    # middlewares
    # setup_swagger(app, swagger_url=prefix+"/doc")


__all__ = [
    'API_MAJOR_VERSION',
    'API_URL_PREFIX',
    'setup_rest',
    'api_specification_path'
]
