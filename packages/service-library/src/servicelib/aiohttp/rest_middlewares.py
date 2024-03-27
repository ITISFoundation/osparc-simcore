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

from ..error_codes import create_error_code
from ..json_serialization import json_dumps, safe_json_loads
from ..mimetype_constants import MIMETYPE_APPLICATION_JSON
from .rest_models import ErrorDetail, LogMessage, ResponseErrorBody
from .rest_responses import create_enveloped_response, create_error_response
from .rest_utils import EnvelopeFactory
from .typing_extension import Handler, Middleware

_DEFAULT_API_VERSION = "v0"
MSG_INTERNAL_ERROR_USER_FRIENDLY_TEMPLATE = "Oops! Something went wrong, but we've noted it down and we'll sort it out ASAP. Thanks for your patience! [{}]"


_logger = logging.getLogger(__name__)


def _is_api_request(request: web.Request, api_version: str) -> bool:
    base_path = "/" + api_version.lstrip("/")
    return bool(request.path.startswith(base_path))


async def _handle_http_successful(
    request: web.BaseRequest, err: web.HTTPSuccessful
) -> web.Response:
    """
    Normalizes HTTPErrors used as `raise web.HTTPOk(reason="I am happy")`
    creating an enveloped json-response
    """
    assert request  # nosec
    assert err.reason  # nosec
    assert str(err) == err.reason  # nosec

    if not err.empty_body:
        # By default exists if class method empty_body==False
        assert err.text  # nosec

        if err.text and not safe_json_loads(err.text):
            # NOTE:
            # - aiohttp defaults `text={status}: {reason}` if not explictly defined and reason defaults
            #   in http.HTTPStatus().phrase if not explicitly defined
            # - These are scenarios created by a lack of
            #   consistency on how we respond in the request handlers.
            #   This overhead can be avoided by having a more strict
            #   response policy.
            # - Moreover there is an *concerning* asymmetry on how these responses are handled
            #   depending whether the are returned or raised!!!!
            err.text = json_dumps({"data": err.reason})
        err.content_type = MIMETYPE_APPLICATION_JSON

    return err


async def _handle_http_error(
    request: web.BaseRequest, err: web.HTTPError
) -> web.Response:
    """
    Normalizes HTTPErrors used as `raise web.HTTPUnauthorized(reason=MSG_USER_EXPIRED)`
    creating an enveloped json-response
    """
    assert request  # nosec
    assert err.reason  # nosec
    assert str(err) == err.reason  # nosec

    if not err.empty_body:
        # By default exists if class method empty_body==False
        assert err.text  # nosec

        if err.text and not safe_json_loads(err.text):
            error_body = ResponseErrorBody(
                message=err.reason,  # we do not like default text=`{status}: {reason}`
                status=err.status,
                errors=[ErrorDetail.from_exception(err)],
                logs=[LogMessage(message=err.reason, level="ERROR")],
            )
            err.text = EnvelopeFactory(error=error_body).as_text()
        err.content_type = MIMETYPE_APPLICATION_JSON

    return err


async def _handle_unexpected_exception(
    request: web.BaseRequest, err: Exception
) -> web.Response:
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
        errors=None,  # avoid details
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
    return resp


def error_middleware_factory(
    api_version: str,
) -> Middleware:
    @web.middleware
    async def _middleware_handler(request: web.Request, handler: Handler):
        """
        Ensure all error raised are properly enveloped and json responses
        """
        # pylint: ignore=too-many-return-statements
        if not _is_api_request(request, api_version):
            return await handler(request)

        try:

            try:
                return await handler(request)

            # NOTE: RETURN  and do NOT RAISE a response in exception handlers
            except web.HTTPSuccessful as err_resp:  # 2XX
                return await _handle_http_successful(request, err_resp)

            except web.HTTPRedirection as err_resp:  # 3XX
                _logger.debug("Redirecting to '%s'", err_resp)
                return err_resp

            except web.HTTPError as err_resp:  # 5XX
                return await _handle_http_error(request, err_resp)

            except NotImplementedError as err:
                return create_error_response(
                    err,
                    http_error_cls=web.HTTPNotImplemented,
                )

            except asyncio.TimeoutError as err:
                return create_error_response(
                    err,
                    http_error_cls=web.HTTPGatewayTimeout,
                )

        except Exception as err:  # pylint: disable=broad-except
            return await _handle_unexpected_exception(request, err)

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
