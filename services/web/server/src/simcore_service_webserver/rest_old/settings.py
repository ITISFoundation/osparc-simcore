import logging

from aiohttp import hdrs

from ._generated_code.models.base_model_ import Model
from .middlewares import (
    Jsonify, jsonify,
    handle_errors
)
from . import routing

log = logging.getLogger(__name__)


def setup_rest(app):
    """Setup the rest API module in the application in aiohttp fashion. """
    log.debug("Setting up %s ...", __name__)

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


__all__ = (
    'setup_rest'
)
