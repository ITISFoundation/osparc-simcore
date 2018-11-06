""" Middlewares for rest-api submodule

"""

import json
import logging

from aiohttp import web
import attr

from .response_utils import is_enveloped, wrap_as_envelope
from .rest_models import ErrorItemType, ErrorType, LogMessageType
from .rest_utils import EnvelopeFactory

log = logging.getLogger(__name__)

class DataEncoder(json.JSONEncoder):
    def default(self, o): #pylint: disable=E0202
        if attr.has(o.__class__):
            return attr.asdict(o)
        return json.JSONEncoder.default(self, o)

def jsonify(payload):
    return json.dumps(payload, cls=DataEncoder)


def is_api_request(request: web.Request, api_basepath: str) -> bool:
    return request.path.startswith(api_basepath)


def error_middleware_factory(api_basepath: str="/v0"):
    @web.middleware
    async def _middleware(request: web.Request, handler):
        """
            Ensure all error raised are properly enveloped and json responses
        """
        if not is_api_request(request, api_basepath):
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
    return _middleware


def envelope_middleware_factory(api_version: str="/v0"):
    @web.middleware
    async def _middleware(request: web.Request, handler):
        """
            Ensures all responses are enveloped as {'data': .. , 'error', ...} as json
        """
        if not is_api_request(request, api_version):
            return await handler(request)

        resp = await handler(request)

        if not isinstance(resp, web.Response):
            data = resp
            try:
                if not is_enveloped(data):
                    payload = wrap_as_envelope(data)
                else:
                    payload = data
                response = web.json_response(payload, dumps=jsonify)

            except (TypeError, ValueError) as err:
                # TODO: assumes openapi error model!!!
                error = ErrorType(
                    errors=[ErrorItemType.from_error(err), ],
                    status=web.HTTPInternalServerError.status_code
                )
                response = web.HTTPInternalServerError(
                    reason = str(err),
                    text=EnvelopeFactory(error=error).as_text(),
                    content_type='application/json'
                )
        else:
            # Enforced by user. Should check it is json?
            response = resp
        return response
    return _middleware
