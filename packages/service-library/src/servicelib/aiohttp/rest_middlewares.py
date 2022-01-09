""" rest - middlewares for error, enveloping and validation

    SEE  https://gist.github.com/amitripshtos/854da3f4217e3441e8fceea85b0cbd91
"""
import json
import logging
from typing import Awaitable, Callable, Union

from aiohttp import web
from aiohttp.web_request import Request
from aiohttp.web_response import StreamResponse
from openapi_core.schema.exceptions import OpenAPIError

from ..utils import is_production_environ
from .rest_models import ErrorItemType, ErrorType, LogMessageType
from .rest_responses import (
    JSON_CONTENT_TYPE,
    _DataType,
    create_data_response,
    create_error_response,
    is_enveloped_from_map,
    is_enveloped_from_text,
    wrap_as_envelope,
)
from .rest_utils import EnvelopeFactory
from .rest_validators import OpenApiValidator
from .typing_extension import Handler, Middleware

DEFAULT_API_VERSION = "v0"


logger = logging.getLogger(__name__)


def is_api_request(request: web.Request, api_version: str) -> bool:
    base_path = "/" + api_version.lstrip("/")
    return request.path.startswith(base_path)


def error_middleware_factory(api_version: str, log_exceptions=True) -> Middleware:

    _is_prod: bool = is_production_environ()

    def _process_and_raise_unexpected_error(request: web.BaseRequest, err: Exception):
        resp = create_error_response(
            err,
            "Unexpected Server error",
            web.HTTPInternalServerError,
            skip_internal_error_details=_is_prod,
        )

        if log_exceptions:
            logger.error(
                'Unexpected server error "%s" from access: %s "%s %s". Responding with status %s',
                type(err),
                request.remote,
                request.method,
                request.path,
                resp.status,
                exc_info=err,
                stack_info=True,
            )
        raise resp

    @web.middleware
    async def _middleware_handler(request: web.Request, handler: Handler):
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
                err.set_status(err.status_code, reason="Unexpected error")

            err.content_type = JSON_CONTENT_TYPE

            if not err.text or not is_enveloped_from_text(err.text):
                error = ErrorType(
                    errors=[
                        ErrorItemType.from_error(err),
                    ],
                    status=err.status,
                    logs=[
                        LogMessageType(message=err.reason, level="ERROR"),
                    ],
                    message=err.reason,
                )
                err.text = EnvelopeFactory(error=error).as_text()

            raise

        except web.HTTPSuccessful as ex:
            ex.content_type = JSON_CONTENT_TYPE
            if ex.text:
                try:
                    payload = json.loads(ex.text)
                    if not is_enveloped_from_map(payload):
                        payload = wrap_as_envelope(data=payload)
                        ex.text = json.dumps(payload)
                except Exception as err:  # pylint: disable=broad-except
                    _process_and_raise_unexpected_error(request, err)
            raise ex

        except web.HTTPRedirection as ex:
            logger.debug("Redirected to %s", ex)
            raise

        except NotImplementedError as err:
            error_response = create_error_response(
                err,
                str(err),
                web.HTTPNotImplemented,
                skip_internal_error_details=_is_prod,
            )
            raise error_response from err

        except Exception as err:  # pylint: disable=broad-except
            _process_and_raise_unexpected_error(request, err)

    # adds identifier (mostly for debugging)
    _middleware_handler.__middleware_name__ = f"{__name__}.error_{api_version}"

    return _middleware_handler


def validate_middleware_factory(api_version: str) -> Middleware:
    @web.middleware
    async def _middleware_handler(request: web.Request, handler: Handler):
        """
        Validates requests against openapi specs and extracts body, params, etc ...
        Validate response against openapi specs
        """
        if not is_api_request(request, api_version):
            return await handler(request)

        # TODO: move this outside!
        RQ_VALIDATED_DATA_KEYS = ("validated-path", "validated-query", "validated-body")

        try:
            validator = OpenApiValidator.create(request.app, api_version)

            # FIXME: if request is HTTPNotFound, it still goes through middlewares and then validator.check_request fails!!!
            try:
                path, query, body = await validator.check_request(request)

                # Injects validated
                request["validated-path"] = path
                request["validated-query"] = query
                request["validated-body"] = body

            except OpenAPIError:
                logger.debug("Failing openAPI specs", exc_info=1)
                raise

            response = await handler(request)

            # FIXME:  openapi-core fails to validate response when specs are in separate files!
            validator.check_response(response)

        finally:
            for k in RQ_VALIDATED_DATA_KEYS:
                request.pop(k, None)

        return response

    # adds identifier (mostly for debugging)
    _middleware_handler.__middleware_name__ = f"{__name__}.validate_{api_version}"

    return _middleware_handler


_ResponseOrBodyData = Union[StreamResponse, _DataType]
HandlerFlexible = Callable[[Request], Awaitable[_ResponseOrBodyData]]
MiddlewareFlexible = Callable[[Request, HandlerFlexible], Awaitable[StreamResponse]]


def envelope_middleware_factory(api_version: str) -> MiddlewareFlexible:
    # FIXME: This data conversion is very error-prone. Use decorators instead!
    _is_prod: bool = is_production_environ()

    @web.middleware
    async def _middleware_handler(
        request: web.Request, handler: HandlerFlexible
    ) -> StreamResponse:
        """
        Ensures all responses are enveloped as {'data': .. , 'error', ...} in json
        ONLY for API-requests
        """
        if not is_api_request(request, api_version):
            resp = await handler(request)
            assert isinstance(resp, StreamResponse)  # nosec
            return resp

        # NOTE: the return values of this handler
        resp: _ResponseOrBodyData = await handler(request)

        if isinstance(resp, web.FileResponse):
            return resp

        if not isinstance(resp, StreamResponse):
            resp = create_data_response(
                data=resp,
                skip_internal_error_details=_is_prod,
            )

        assert isinstance(resp, web.StreamResponse)  # nosec
        return resp

    # adds identifier (mostly for debugging)
    _middleware_handler.__middleware_name__ = f"{__name__}.envelope_{api_version}"

    return _middleware_handler


def append_rest_middlewares(
    app: web.Application, api_version: str = DEFAULT_API_VERSION
):
    """Helper that appends rest-middlewares in the correct order"""
    app.middlewares.append(error_middleware_factory(api_version))
    # FIXME:  openapi-core fails to validate response when specs are in separate files!
    # FIXME: disabled so webserver and storage do not get this issue
    # app.middlewares.append(validate_middleware_factory(api_version))
    app.middlewares.append(envelope_middleware_factory(api_version))
