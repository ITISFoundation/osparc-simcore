"""rest - middlewares for error, enveloping and validation

SEE  https://gist.github.com/amitripshtos/854da3f4217e3441e8fceea85b0cbd91
"""

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from aiohttp import web
from aiohttp.web_exceptions import HTTPError
from aiohttp.web_request import Request
from aiohttp.web_response import StreamResponse
from common_library.error_codes import create_error_code
from common_library.json_serialization import json_dumps, json_loads
from models_library.rest_error import ErrorGet, ErrorItemType, LogMessageType

from ..logging_errors import create_troubleshotting_log_kwargs
from ..mimetype_constants import MIMETYPE_APPLICATION_JSON
from ..rest_responses import is_enveloped_from_map, is_enveloped_from_text
from ..utils import is_production_environ
from . import status
from .rest_responses import (
    create_data_response,
    create_http_error,
    safe_status_message,
    wrap_as_envelope,
)
from .rest_utils import EnvelopeFactory
from .typing_extension import Handler, Middleware
from .web_exceptions_extension import get_http_error_class_or_none

DEFAULT_API_VERSION = "v0"
_FMSG_INTERNAL_ERROR_USER_FRIENDLY = (
    "We apologize for the inconvenience. "
    "The issue has been recorded, please report it if it persists."
)


_logger = logging.getLogger(__name__)


def is_api_request(request: web.Request, api_version: str) -> bool:
    base_path = "/" + api_version.lstrip("/")
    return bool(request.path.startswith(base_path))


def _handle_unexpected_exception_as_500(
    request: web.BaseRequest,
    exception: Exception,
    *,
    skip_internal_error_details: bool,
) -> web.HTTPInternalServerError:
    """Process unexpected exceptions and return them as HTTP errors with proper formatting.

    IMPORTANT: this function cannot throw exceptions, as it is called
    """
    error_code = create_error_code(exception)
    error_context: dict[str, Any] = {
        "request.remote": f"{request.remote}",
        "request.method": f"{request.method}",
        "request.path": f"{request.path}",
    }

    user_error_msg = _FMSG_INTERNAL_ERROR_USER_FRIENDLY

    http_error = create_http_error(
        exception,
        user_error_msg,
        web.HTTPInternalServerError,
        skip_internal_error_details=skip_internal_error_details,
        error_code=error_code,
    )

    error_context["http_error"] = http_error

    _logger.exception(
        **create_troubleshotting_log_kwargs(
            user_error_msg,
            error=exception,
            error_context=error_context,
            error_code=error_code,
        )
    )
    return http_error


def _handle_http_error(
    request: web.BaseRequest, exception: web.HTTPError
) -> web.HTTPError:
    """Handle standard HTTP errors by ensuring they're properly formatted."""
    assert request  # nosec
    exception.content_type = MIMETYPE_APPLICATION_JSON
    if exception.reason:
        exception.set_status(
            exception.status, safe_status_message(message=exception.reason)
        )

    if not exception.text or not is_enveloped_from_text(exception.text):
        error_message = exception.text or exception.reason or "Unexpected error"
        error_model = ErrorGet(
            errors=[
                ErrorItemType.from_error(exception),
            ],
            status=exception.status,
            logs=[
                LogMessageType(message=error_message, level="ERROR"),
            ],
            message=error_message,
        )
        exception.text = EnvelopeFactory(error=error_model).as_text()

    return exception


def _handle_http_successful(
    request: web.Request, exception: web.HTTPSuccessful
) -> web.HTTPSuccessful:
    """Handle successful HTTP responses, ensuring they're properly enveloped."""
    assert request  # nosec

    exception.content_type = MIMETYPE_APPLICATION_JSON
    if exception.reason:
        exception.set_status(
            exception.status, safe_status_message(message=exception.reason)
        )

    if exception.text:
        payload = json_loads(exception.text)
        if not is_enveloped_from_map(payload):
            payload = wrap_as_envelope(data=payload)
            exception.text = json_dumps(payload)

    return exception


def _handle_exception_as_http_error(
    request: web.Request,
    exception: Exception,
    status_code: int,
    *,
    skip_internal_error_details: bool,
) -> HTTPError:
    """
    Generic handler for exceptions that map to specific HTTP status codes.
    Converts the status code to the appropriate HTTP error class and creates a response.
    """
    assert request  # nosec

    http_error_cls = get_http_error_class_or_none(status_code)
    if http_error_cls is None:
        msg = (
            f"No HTTP error class found for status code {status_code}, falling back to 500",
        )
        raise ValueError(msg)

    return create_http_error(
        exception,
        f"{exception}",
        http_error_cls,
        skip_internal_error_details=skip_internal_error_details,
    )


def error_middleware_factory(api_version: str) -> Middleware:
    _is_prod: bool = is_production_environ()

    @web.middleware
    async def _middleware_handler(request: web.Request, handler: Handler):
        """
        Ensure all error raised are properly enveloped and json responses
        """
        if not is_api_request(request, api_version):
            return await handler(request)

        try:
            try:
                result = await handler(request)

            except web.HTTPError as exc:  # 4XX and 5XX raised as exceptions
                result = _handle_http_error(request, exc)

            except web.HTTPSuccessful as exc:  # 2XX rased as exceptions
                result = _handle_http_successful(request, exc)

            except web.HTTPRedirection as exc:  # 3XX raised as exceptions
                result = exc

            except NotImplementedError as exc:
                result = _handle_exception_as_http_error(
                    request,
                    exc,
                    status.HTTP_501_NOT_IMPLEMENTED,
                    skip_internal_error_details=_is_prod,
                )

            except TimeoutError as exc:
                result = _handle_exception_as_http_error(
                    request,
                    exc,
                    status.HTTP_504_GATEWAY_TIMEOUT,
                    skip_internal_error_details=_is_prod,
                )

        except Exception as exc:  # pylint: disable=broad-except
            #
            # Last resort for unexpected exceptions (including those raise by the exception handlers!)
            #
            result = _handle_unexpected_exception_as_500(
                request, exc, skip_internal_error_details=_is_prod
            )

        return result

    # adds identifier (mostly for debugging)
    setattr(  # noqa: B010
        _middleware_handler, "__middleware_name__", f"{__name__}.error_{api_version}"
    )

    return _middleware_handler


_ResponseOrBodyData = StreamResponse | Any
HandlerFlexible = Callable[[Request], Awaitable[_ResponseOrBodyData]]
MiddlewareFlexible = Callable[[Request, HandlerFlexible], Awaitable[StreamResponse]]


def envelope_middleware_factory(
    api_version: str,
) -> Callable[..., Awaitable[StreamResponse]]:
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
        resp = await handler(request)

        if isinstance(resp, web.FileResponse):
            return resp

        if not isinstance(resp, StreamResponse):
            resp = create_data_response(data=resp)

        assert isinstance(resp, web.StreamResponse)  # nosec
        return resp

    # adds identifier (mostly for debugging)
    setattr(  # noqa: B010
        _middleware_handler, "__middleware_name__", f"{__name__}.envelope_{api_version}"
    )

    return _middleware_handler


def append_rest_middlewares(
    app: web.Application, api_version: str = DEFAULT_API_VERSION
):
    """Helper that appends rest-middlewares in the correct order"""
    app.middlewares.append(error_middleware_factory(api_version))
    app.middlewares.append(envelope_middleware_factory(api_version))
