""" Middlewares for rest-api submodule

"""

import json
import logging

from aiohttp import web

from .rest_models import ErrorItemType, ErrorType, LogMessageType
from .rest_utils import EnvelopeFactory

log = logging.getLogger(__name__)

def is_enveloped(payload):
    if isinstance(payload, str):
        try:
            return is_enveloped(json.loads(payload))
        except Exception: #pylint: disable=W0703
            return False
    return isinstance(payload, dict) and set(payload.keys()) == {'data', 'error'}



@web.middleware
async def error_middleware(request: web.Request, handler):
    """
        Ensure all error raised are properly enveloped and json responses
    """
    # FIXME: bypass if not api. create decorator!?
    if 'v0' not in request.path:
        return await handler(request)

    # FIXME: review when to send info to client and when not!
    try:
        response = await handler(request)
        return response
    except web.HTTPError as err:
        # TODO: differenciate between server/client error
        if not err.reason:
            err.reason = "Unexpected error"

        if not err.content_type == 'application/json':
            err.content_type = 'application/json'

        if not err.text or not is_enveloped(err.text):
            error = ErrorType(
                errors=[ErrorItemType.from_error(err), ],
                status=err.status,
                logs=[LogMessageType(message=err.reason, level="ERROR"),]
            )
            err.text = EnvelopeFactory(error=error).as_text()

        raise
    except web.HTTPSuccessful as ex:
        ex.content_type = 'application/json'
        if ex.text and not is_enveloped(ex.text):
            ex.text = EnvelopeFactory(error=ex.text).as_text()
        raise
    except web.HTTPRedirection as ex:
        log.debug("Redirection %s", ex)
        raise
    except Exception as err:  #pylint: disable=W0703
        # TODO: send info only in debug mode
        error = ErrorType(
            errors=[ErrorItemType.from_error(err), ],
            status=web.HTTPInternalServerError.status_code
        )
        raise web.HTTPInternalServerError(
                reason="Internal server error",
                text=EnvelopeFactory(error=error).as_text(),
                content_type='application/json',
            )

@web.middleware
async def envelope_middleware(request: web.Request, handler):
    """
        Ensures all responses are enveloped as {'data': .. , 'error', ...} as json
    """
    # FIXME: bypass if not api
    if 'v0' not in request.path:
        return await handler(request)

    resp = await handler(request)

    if not isinstance(resp, web.Response):
        try:
            if not is_enveloped(resp):
                enveloped = EnvelopeFactory(data=resp).as_dict()
                response = web.json_response(data=enveloped)
            else:
                response = web.json_response(data=resp)
        except TypeError as err:
            error = ErrorType(
                errors=[ErrorItemType.from_error(err), ],
                status=web.HTTPInternalServerError.status_code
            )
            web.HTTPInternalServerError(
                reason = str(err),
                text=EnvelopeFactory(error=error).as_text(),
                content_type='application/json'
            )
    else:
        response = resp
    return response
