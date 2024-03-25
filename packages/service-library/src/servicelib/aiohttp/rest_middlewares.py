""" rest - middlewares for error, enveloping and validation

    SEE  https://gist.github.com/amitripshtos/854da3f4217e3441e8fceea85b0cbd91
"""
import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Any, Union

from aiohttp import web
from aiohttp.web_request import Request
from aiohttp.web_response import StreamResponse
from servicelib.error_codes import create_error_code

from ..mimetype_constants import MIMETYPE_APPLICATION_JSON
from .rest_models import ErrorDetail, LogMessage, ResponseErrorBody
from .rest_responses import (
    create_enveloped_response,
    create_error_response,
    is_enveloped_from_text,
)
from .rest_utils import EnvelopeFactory
from .typing_extension import Handler, Middleware

_DEFAULT_API_VERSION = "v0"
MSG_INTERNAL_ERROR_USER_FRIENDLY_TEMPLATE = "Oops! Something went wrong, but we've noted it down and we'll sort it out ASAP. Thanks for your patience! [{}]"


_logger = logging.getLogger(__name__)


def _is_api_request(request: web.Request, api_version: str) -> bool:
    base_path = "/" + api_version.lstrip("/")
    return bool(request.path.startswith(base_path))


def _handle_http_error_and_reraise(request: web.BaseRequest, err: web.HTTPError):
    """Ensures response for a web.HTTPError is complete"""
    assert request  # nosec
    assert err.reason  # nosec

    err.content_type = MIMETYPE_APPLICATION_JSON
    if not err.empty_body and (not err.text or not is_enveloped_from_text(err.text)):
        # Ensure json-body
        error_body = ResponseErrorBody(
            errors=[
                ErrorDetail.from_exception(err),
            ],
            status=err.status,
            logs=[
                LogMessage(message=err.reason, level="ERROR"),
            ],
            message=err.reason,
        )
        err.text = EnvelopeFactory(error=error_body).as_text()

    raise err


def _handle_unexpected_error_and_reraise(request: web.BaseRequest, err: Exception):
    """
    This error handler is the last resource to catch unhandled exceptions. When
    an exception reaches this point, it is converted into a web.HTTPInternalServerError
    reponse (i.e. HTTP_500_INTERNAL_ERROR) for the client and the server logs
    the error to be diagnosed

    Its purpose is:
        - respond the client with 500 and a reference OEC
        - log sufficient information to diagnose the issue
    """
    error_code = create_error_code(err)
    resp = create_error_response(
        errors=[],  # avoid details
        message=MSG_INTERNAL_ERROR_USER_FRIENDLY_TEMPLATE.format(error_code),
        http_error_cls=web.HTTPInternalServerError,
    )
    _logger.exception(
        "Request %s raised '%s' [%s]%s",
        f"'{request.method} {request.path}'",
        type(err).__name__,
        error_code,
        f"\n {request.remote=}\n request.headers={dict(request.raw_headers)}",
        extra={"error_code": error_code},
    )
    raise resp


def error_middleware_factory(
    api_version: str,
) -> Middleware:
    @web.middleware
    async def _middleware_handler(request: web.Request, handler: Handler):
        """
        Ensure all error raised are properly enveloped and json responses
        """
        if not _is_api_request(request, api_version):
            return await handler(request)

        try:
            return await handler(request)

        except web.HTTPError as err:
            _handle_http_error_and_reraise(request, err)

        except (web.HTTPRedirection, web.HTTPSuccessful) as err:
            _logger.debug("Gone through error middleware %s", err)
            raise

        except NotImplementedError as err:
            error_response = create_error_response(
                err,
                http_error_cls=web.HTTPNotImplemented,
            )
            raise error_response from err

        except asyncio.TimeoutError as err:
            error_response = create_error_response(
                err,
                http_error_cls=web.HTTPGatewayTimeout,
            )
            raise error_response from err

        except Exception as err:  # pylint: disable=broad-except
            _handle_unexpected_error_and_reraise(request, err)

    # adds identifier (mostly for debugging)
    _middleware_handler.__middleware_name__ = f"{__name__}.error_{api_version}"

    return _middleware_handler  # type: ignore[no-any-return]


_ResponseOrBodyData = Union[StreamResponse, Any]
HandlerFlexible = Callable[[Request], Awaitable[_ResponseOrBodyData]]
MiddlewareFlexible = Callable[[Request, HandlerFlexible], Awaitable[StreamResponse]]


def envelope_middleware_factory(api_version: str) -> MiddlewareFlexible:
    # FIXME: This data conversion is very error-prone. Use decorators instead!!!

    @web.middleware
    async def _middleware_handler(
        request: web.Request, handler: HandlerFlexible
    ) -> StreamResponse:
        """
        Ensures all responses are enveloped as {'data': .. , 'error', ...} in json
        ONLY for API-requests
        """
        if not _is_api_request(request, api_version):
            resp = await handler(request)
            assert isinstance(resp, StreamResponse)  # nosec
            return resp

        # NOTE: the values returned by this handle might be direclty data!
        resp_or_data = await handler(request)

        if isinstance(resp_or_data, web.FileResponse):
            return resp_or_data

        if not isinstance(resp_or_data, StreamResponse):
            # NOTE: ensures envelopes if data is returned
            # NOTE: at this point any response is expected to be enveloped!!
            resp_or_data = create_enveloped_response(data=resp_or_data)

        assert isinstance(resp_or_data, web.StreamResponse)  # nosec
        return resp_or_data

    # adds identifier (mostly for debugging)
    _middleware_handler.__middleware_name__ = f"{__name__}.envelope_{api_version}"

    return _middleware_handler  # type: ignore[no-any-return]


def append_rest_middlewares(
    app: web.Application, api_version: str = _DEFAULT_API_VERSION
):
    """Helper that appends rest-middlewares in the correct order"""
    app.middlewares.append(error_middleware_factory(api_version))
    app.middlewares.append(envelope_middleware_factory(api_version))
