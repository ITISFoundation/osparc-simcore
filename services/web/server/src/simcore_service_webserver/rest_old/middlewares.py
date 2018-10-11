
from aiohttp import web

from aiohttp_apiset.middlewares import Jsonify, jsonify

from ._generated_code.models.error_enveloped import ErrorEnveloped, Error


@web.middleware
async def handle_errors(request, handler):
    try:
        response = await handler(request)
        return response
    except web.HTTPError as ex:
        # FIXME: need to fit detailed errors
        ee = ErrorEnveloped(
             error = Error(message=ex.reason, errors=[]),
             status=ex.status
            )
        return web.json_response(ee.to_dict(), status=ex.status)

__all__ = [
    "handle_errors",
    "jsonify", "Jsonify"
]
