import logging
from typing import NamedTuple, TypeAlias

from aiohttp import web
from common_library.error_codes import create_error_code
from common_library.json_serialization import json_dumps
from models_library.basic_types import IDStr
from models_library.rest_error import ErrorGet
from servicelib.aiohttp.web_exceptions_extension import get_all_aiohttp_http_exceptions
from servicelib.logging_errors import create_troubleshotting_log_kwargs
from servicelib.status_codes_utils import is_5xx_server_error

from .exceptions_handlers_base import AiohttpExceptionHandler, ExceptionHandlersMap

_logger = logging.getLogger(__name__)


_STATUS_CODE_TO_HTTP_ERRORS: dict[
    int, type[web.HTTPException]
] = get_all_aiohttp_http_exceptions(web.HTTPError)


class _DefaultDict(dict):
    def __missing__(self, key):
        return f"'{key}=?'"


class HttpErrorInfo(NamedTuple):
    """Info provided to auto-create HTTPError"""

    status_code: int
    msg_template: str  # sets HTTPError.reason


ExceptionToHttpErrorMap: TypeAlias = dict[type[BaseException], HttpErrorInfo]


def create_exception_handler_from_http_error(
    status_code: int,
    msg_template: str,
) -> AiohttpExceptionHandler:
    """
    Custom Exception-Handler factory

    Creates a custom `WebApiExceptionHandler` that maps specific exception to a given http status code error

    Given an `ExceptionToHttpErrorMap`, this function returns a handler that checks if an exception
    matches one in the map, returning an HTTP error with the mapped status code and message.
    Server errors (5xx) include additional logging with request context. Unmapped exceptions are
    returned as-is for re-raising.

    Arguments:
        status_code: the http status code to associate at the web-api interface to this error
        msg_template: a template string to pass to the HttpError

    Returns:
        A web api exception handler
    """

    async def _exception_handler(
        request: web.Request,
        exception: BaseException,
    ) -> web.Response:

        # safe formatting, i.e. does not raise
        user_msg = msg_template.format_map(
            _DefaultDict(getattr(exception, "__dict__", {}))
        )

        error = ErrorGet(msg=user_msg)

        if is_5xx_server_error(status_code):
            oec = create_error_code(exception)
            _logger.exception(
                **create_troubleshotting_log_kwargs(
                    user_msg,
                    error=exception,
                    error_code=oec,
                    error_context={
                        "request": request,
                        "request.remote": f"{request.remote}",
                        "request.method": f"{request.method}",
                        "request.path": f"{request.path}",
                    },
                )
            )
            error = ErrorGet(msg=user_msg, support_id=IDStr(oec))

        return web.json_response(
            data={"error": error.model_dump(exclude_unset=True, mode="json")},
            dumps=json_dumps,
            reason=user_msg,
            status=status_code,
        )

    return _exception_handler


def to_exceptions_handlers_map(
    exc_to_http_error_map: ExceptionToHttpErrorMap,
) -> ExceptionHandlersMap:
    """Converts { exc_type: (status, msg), ... }  -> { exc_type: callable, ... }"""
    exc_handlers_map: ExceptionHandlersMap = {
        exc_type: create_exception_handler_from_http_error(
            status_code=info.status_code, msg_template=info.msg_template
        )
        for exc_type, info in exc_to_http_error_map.items()
    }

    return exc_handlers_map
