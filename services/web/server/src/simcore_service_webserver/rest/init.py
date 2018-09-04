from aiohttp import hdrs, web

from .middlewares import (
    Jsonify, jsonify,
    handle_errors
)

from .generated_code_.models.base_model_ import Model

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
    "setup_rest"
]
