"""rest - middlewares for error, enveloping and validation

SEE  https://gist.github.com/amitripshtos/854da3f4217e3441e8fceea85b0cbd91
"""

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from aiohttp import web
from aiohttp.web_request import Request
from aiohttp.web_response import StreamResponse
from common_library.error_codes import create_error_code
from common_library.json_serialization import json_dumps, json_loads
from models_library.rest_error import ErrorGet, ErrorItemType, LogMessageType

from ..logging_errors import create_troubleshotting_log_kwargs
from ..mimetype_constants import MIMETYPE_APPLICATION_JSON
from ..rest_responses import is_enveloped_from_map, is_enveloped_from_text
from ..utils import is_production_environ
from .rest_responses import (
    create_data_response,
    create_http_error,
    safe_status_message,
    wrap_as_envelope,
)
from .rest_utils import EnvelopeFactory
from .typing_extension import Handler, Middleware

DEFAULT_API_VERSION = "v0"
_FMSG_INTERNAL_ERROR_USER_FRIENDLY = (
    "We apologize for the inconvenience. "
    "The issue has been recorded, please report it if it persists."
)


_logger = logging.getLogger(__name__)


def is_api_request(request: web.Request, api_version: str) -> bool:
    base_path = "/" + api_version.lstrip("/")
    return bool(request.path.startswith(base_path))


def _process_and_raise_unexpected_error(
    request: web.BaseRequest, err: Exception, *, skip_internal_error_details: bool
):
    """Process unexpected exceptions and raise them as HTTP errors with proper formatting."""
    error_code = create_error_code(err)
    error_context: dict[str, Any] = {
        "request.remote": f"{request.remote}",
        "request.method": f"{request.method}",
        "request.path": f"{request.path}",
    }

    user_error_msg = _FMSG_INTERNAL_ERROR_USER_FRIENDLY
    http_error = create_http_error(
        err,
        user_error_msg,
        web.HTTPInternalServerError,
        skip_internal_error_details=skip_internal_error_details,
        error_code=error_code,
    )
    _logger.exception(
        **create_troubleshotting_log_kwargs(
            user_error_msg,
            error=err,
            error_context=error_context,
            error_code=error_code,
        )
    )
    raise http_error


def _handle_http_error(err: web.HTTPError) -> None:
    """Handle standard HTTP errors by ensuring they're properly formatted."""
    err.content_type = MIMETYPE_APPLICATION_JSON
    if err.reason:
        err.set_status(err.status, safe_status_message(message=err.reason))

    if not err.text or not is_enveloped_from_text(err.text):
        error_message = err.text or err.reason or "Unexpected error"
        error_model = ErrorGet(
            errors=[
                ErrorItemType.from_error(err),
            ],
            status=err.status,
            logs=[
                LogMessageType(message=error_message, level="ERROR"),
            ],
            message=error_message,
        )
        err.text = EnvelopeFactory(error=error_model).as_text()


def _handle_http_successful(
    err: web.HTTPSuccessful, request: web.Request, *, skip_internal_error_details: bool
) -> None:
    """Handle successful HTTP responses, ensuring they're properly enveloped."""
    err.content_type = MIMETYPE_APPLICATION_JSON
    if err.reason:
        err.set_status(err.status, safe_status_message(message=err.reason))

    if err.text:
        try:
            payload = json_loads(err.text)
            if not is_enveloped_from_map(payload):
                payload = wrap_as_envelope(data=payload)
                err.text = json_dumps(payload)
        except Exception as other_error:  # pylint: disable=broad-except
            _process_and_raise_unexpected_error(
                request,
                other_error,
                skip_internal_error_details=skip_internal_error_details,
            )


def _handle_not_implemented(
    err: NotImplementedError, *, skip_internal_error_details: bool
) -> None:
    """Handle NotImplementedError by converting to appropriate HTTP error."""
    http_error = create_http_error(
        err,
        f"{err}",
        web.HTTPNotImplemented,
        skip_internal_error_details=skip_internal_error_details,
    )
    raise http_error from err


def _handle_timeout(err: TimeoutError, *, skip_internal_error_details: bool) -> None:
    """Handle TimeoutError by converting to appropriate HTTP error."""
    http_error = create_http_error(
        err,
        f"{err}",
        web.HTTPGatewayTimeout,
        skip_internal_error_details=skip_internal_error_details,
    )
    raise http_error from err


def error_middleware_factory(  # noqa: C901
    api_version: str,
) -> Middleware:
    _is_prod: bool = is_production_environ()

    @web.middleware
    async def _middleware_handler(request: web.Request, handler: Handler):  # noqa: C901
        """
        Ensure all error raised are properly enveloped and json responses
        """
        if not is_api_request(request, api_version):
            return await handler(request)

        # FIXME: review when to send info to client and when not!
        try:
            return await handler(request)

        except web.HTTPError as err:
            _handle_http_error(err)
            raise

        except web.HTTPSuccessful as err:
            _handle_http_successful(err, request, skip_internal_error_details=_is_prod)
            raise

        except web.HTTPRedirection as err:
            _logger.debug("Redirected to %s", err)
            raise

        except NotImplementedError as err:
            _handle_not_implemented(err, skip_internal_error_details=_is_prod)

        except TimeoutError as err:
            _handle_timeout(err, skip_internal_error_details=_is_prod)

        except Exception as err:  # pylint: disable=broad-except
            _process_and_raise_unexpected_error(
                request, err, skip_internal_error_details=_is_prod
            )

    # adds identifier (mostly for debugging)
    _middleware_handler.__middleware_name__ = f"{__name__}.error_{api_version}"

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
