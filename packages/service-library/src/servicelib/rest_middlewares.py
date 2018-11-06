""" rest - middlewares for error, enveloping and validation


"""
import logging

from aiohttp import web

from .rest_models import ErrorItemType, ErrorType, LogMessageType
from .rest_responses import create_data_response, is_enveloped, JSON_CONTENT_TYPE
from .rest_utils import EnvelopeFactory
from .rest_validators import OpenApiValidator

DEFAULT_API_VERSION = "v0"


logger = logging.getLogger(__name__)


def is_api_request(request: web.Request, api_version: str) -> bool:
    base_path = "/" + api_version.lstrip("/")
    return request.path.startswith(base_path)


def error_middleware_factory(api_version: str = DEFAULT_API_VERSION):
    @web.middleware
    async def _middleware(request: web.Request, handler):
        """
            Ensure all error raised are properly enveloped and json responses
        """
        if not is_api_request(request, api_version):
            return await handler(request)

        # FIXME: review when to send info to client and when not!
        try:
            response = await handler(request)
            return response
        except web.HTTPError as err:
            # TODO: differenciate between server/client error
            if not err.reason:
                err.reason = "Unexpected error"

            if not err.content_type == JSON_CONTENT_TYPE:
                err.content_type = JSON_CONTENT_TYPE

            if not err.text or not is_enveloped(err.text):
                error = ErrorType(
                    errors=[ErrorItemType.from_error(err), ],
                    status=err.status,
                    logs=[LogMessageType(message=err.reason, level="ERROR"), ]
                )
                err.text = EnvelopeFactory(error=error).as_text()

            raise
        except web.HTTPSuccessful as ex:
            ex.content_type = JSON_CONTENT_TYPE
            if ex.text and not is_enveloped(ex.text):
                ex.text = EnvelopeFactory(error=ex.text).as_text()
            raise
        except web.HTTPRedirection as ex:
            logger.debug("Redirection %s", ex)
            raise
        except Exception as err:  # pylint: disable=W0703
            # TODO: send info only in debug mode
            error = ErrorType(
                errors=[ErrorItemType.from_error(err), ],
                status=web.HTTPInternalServerError.status_code
            )
            raise web.HTTPInternalServerError(
                reason="Internal server error",
                text=EnvelopeFactory(error=error).as_text(),
                content_type=JSON_CONTENT_TYPE,
            )
    return _middleware


def validate_middleware_factory(api_version: str = DEFAULT_API_VERSION):
    @web.middleware
    async def _middleware(request: web.Request, handler):
        """
            Validates requests against openapi specs and extracts body, params, etc ...
            Validate response against openapi specs
        """
        if not is_api_request(request, api_version):
            return await handler(request)

        # TODO: move this outside!
        RQ_VALIDATED_DATA_KEYS = (
            "validated-path", "validated-query", "validated-body")

        try:
            validator = OpenApiValidator.create(request.app, api_version)
            path, query, body = await validator.check_request(request)

            # TODO: simplify!!!!
            # Injects validated
            request["validated-path"] = path
            request["validated-query"] = query
            request["validated-body"] = body

            response = await handler(request)
            validator.check_response(response)

        finally:
            for k in RQ_VALIDATED_DATA_KEYS:
                request.pop(k)

        return response

    return _middleware


def envelope_middleware_factory(api_version: str = DEFAULT_API_VERSION):
    @web.middleware
    async def _middleware(request: web.Request, handler):
        """
            Ensures all responses are enveloped as {'data': .. , 'error', ...} in json
        """
        if not is_api_request(request, api_version):
            return await handler(request)

        resp = await handler(request)

        if not isinstance(resp, web.Response):
            response = create_data_response(data=resp)
        else:
            # Enforced by user. Should check it is json?
            response = resp
        return response
    return _middleware


def append_rest_middlewares(app: web.Application, api_version: str = DEFAULT_API_VERSION):
    """ Helper that appends rest-middlewares in the correct order

    """
    app.middlewares.append(error_middleware_factory(api_version))
    app.middlewares.append(validate_middleware_factory(api_version))
    app.middlewares.append(envelope_middleware_factory(api_version))
