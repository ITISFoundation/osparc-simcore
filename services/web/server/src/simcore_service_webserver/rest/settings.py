import logging
from pathlib import Path

from aiohttp import hdrs
import yaml

from ._generated_code.models.base_model_ import Model
from .middlewares import (
    Jsonify, jsonify,
    handle_errors
)
from . import routing
from .. import resources

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

    # routing
    routing.include_oaspecs_routes(router)
    routing.include_other_routes(router)

    # middlewahres
    # add automatic jsonification of the models located in generated code
    jsonify.singleton = Jsonify(indent=3, ensure_ascii=False)
    jsonify.singleton.add_converter(Model, lambda o: o.to_dict(), score=0)

    app.middlewares.append(jsonify)
    app.middlewares.append(handle_errors)


__all__ = [
    'API_MAJOR_VERSION',
    'API_URL_PREFIX',
    'setup_rest',
    'api_specification_path'
]
