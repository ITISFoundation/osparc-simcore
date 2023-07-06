""" rest - middlewares for error, enveloping and validation

    SEE  https://gist.github.com/amitripshtos/854da3f4217e3441e8fceea85b0cbd91
"""
import asyncio
import json
import logging
from collections.abc import Awaitable, Callable
from typing import Union

from aiohttp import web
from aiohttp.web_request import Request
from aiohttp.web_response import StreamResponse

from ..mimetype_constants import MIMETYPE_APPLICATION_JSON
from ..utils import is_production_environ
from .rest_models import ErrorItemType, ErrorType, LogMessageType
from .rest_responses import (
    Any,
    create_data_response,
    create_error_response,
    is_enveloped_from_map,
    is_enveloped_from_text,
    wrap_as_envelope,
)
from .rest_utils import EnvelopeFactory
from .typing_extension import Handler, Middleware

DEFAULT_API_VERSION = "v0"


_logger = logging.getLogger(__name__)


def is_api_request(request: web.Request, api_version: str) -> bool:
    base_path = "/" + api_version.lstrip("/")
    return request.path.startswith(base_path)


def error_middleware_factory(
    api_version: str,
    log_exceptions: bool = True,
) -> Middleware:
    _is_prod: bool = is_production_environ()

    def _process_and_raise_unexpected_error(request: web.BaseRequest, err: Exception):
        resp = create_error_response(
            err,
            "Unexpected Server error",
            web.HTTPInternalServerError,
            skip_internal_error_details=_is_prod,
        )

        if log_exceptions:
            _logger.error(
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
            return await handler(request)

        except web.HTTPError as err:
            # TODO: differenciate between server/client error
            if not err.reason:
                err.set_status(err.status_code, reason="Unexpected error")

            err.content_type = MIMETYPE_APPLICATION_JSON

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

        except web.HTTPSuccessful as err:
            err.content_type = MIMETYPE_APPLICATION_JSON
            if err.text:
                try:
                    payload = json.loads(err.text)
                    if not is_enveloped_from_map(payload):
                        payload = wrap_as_envelope(data=payload)
                        err.text = json.dumps(payload)
                except Exception as err:  # pylint: disable=broad-except
                    _process_and_raise_unexpected_error(request, err)
            raise err

        except web.HTTPRedirection as err:
            _logger.debug("Redirected to %s", err)
            raise

        except NotImplementedError as err:
            error_response = create_error_response(
                err,
                f"{err}",
                web.HTTPNotImplemented,
                skip_internal_error_details=_is_prod,
            )
            raise error_response from err

        except asyncio.TimeoutError as err:
            error_response = create_error_response(
                err,
                f"{err}",
                web.HTTPGatewayTimeout,
                skip_internal_error_details=_is_prod,
            )
            raise error_response from err

        except Exception as err:  # pylint: disable=broad-except
            _process_and_raise_unexpected_error(request, err)

    # adds identifier (mostly for debugging)
    _middleware_handler.__middleware_name__ = f"{__name__}.error_{api_version}"

    return _middleware_handler


_ResponseOrBodyData = Union[StreamResponse, Any]
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
    app.middlewares.append(envelope_middleware_factory(api_version))
