from aiohttp import hdrs

from ._generated_code.models.base_model_ import Model
from .middlewares import (
    Jsonify, jsonify,
    handle_errors
)
from .. import resources


# NOTE: Set here the version of API to be used
# NOTE: Versions and name consistency tested in test_rest.py
API_MAJOR_VERSION = 1
API_URL_PREFIX = "v{:.0f}".format(API_MAJOR_VERSION)
API_SPECS_NAME = ".oas3/{}/openapi.yaml".format(API_URL_PREFIX)

def api_specification_path():
    return resources.get_path(API_SPECS_NAME)

def setup_rest(app):
    """Setup the library in aiohttp fashion."""
    router = app.router

    router.set_cors(app, domains='*', headers=(
        (hdrs.ACCESS_CONTROL_EXPOSE_HEADERS, hdrs.AUTHORIZATION),
    ))

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
