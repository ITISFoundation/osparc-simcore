import logging
from collections.abc import Iterable
from typing import NamedTuple, TypeAlias

from aiohttp import web
from servicelib.aiohttp.web_exceptions_extension import get_all_aiohttp_http_exceptions
from servicelib.logging_errors import create_troubleshotting_log_kwargs
from servicelib.status_codes_utils import is_5xx_server_error

from .exceptions_handlers_base import AiohttpExceptionHandler

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
    exception_cls: type[BaseException],
    *,
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
        exception_cls: exception raise during the request
        status_code: the http status code to associate at the web-api interface to this error
        msg_template: a template string to pass to the HttpError

    Returns:
        A web api exception handler
    """

    async def _exception_handler(
        request: web.Request,
        exception: BaseException,
    ) -> web.Response:
        assert isinstance(exception, exception_cls)  # nosec

        # safe formatting, i.e. does not raise
        user_msg = msg_template.format_map(
            _DefaultDict(getattr(exception, "__dict__", {}))
        )

        if is_5xx_server_error(status_code):
            _logger.exception(
                **create_troubleshotting_log_kwargs(
                    user_msg,
                    error=exception,
                    error_context={
                        "request": request,
                        "request.remote": f"{request.remote}",
                        "request.method": f"{request.method}",
                        "request.path": f"{request.path}",
                    },
                )
            )

        # TODO: make this part customizable? e.g. so we can inject e.g. oec?
        # TODO: connect with ErrorModel
        return web.json_response(
            {
                "error": {
                    "msg": user_msg,
                }
            },
            status=status_code,
        )

    return _exception_handler


def _sort_exceptions_by_specificity(
    exceptions: Iterable[type[BaseException]], *, concrete_first: bool = True
) -> list[type[BaseException]]:
    return sorted(
        exceptions,
        key=lambda exc: sum(issubclass(e, exc) for e in exceptions if e is not exc),
        reverse=not concrete_first,
    )


def create_exception_handler_from_http_error_map(
    exc_to_http_error_map: ExceptionToHttpErrorMap,
) -> AiohttpExceptionHandler:
    """
    Custom Exception-Handler factory

    Creates a custom `WebApiExceptionHandler` that maps one-to-one exception to status code error codes

    Analogous to `create_exception_handler_from_status_code` but ExceptionToHttpErrorMap as input
    """

    _exception_handlers = {
        exc_cls: create_exception_handler_from_http_error(
            exception_cls=exc_cls,
            status_code=http_error_info.status_code,
            msg_template=http_error_info.msg_template,
        )
        for exc_cls, http_error_info in exc_to_http_error_map.items()
    }

    _catch_exceptions = _sort_exceptions_by_specificity(
        list(_exception_handlers.keys())
    )

    async def _exception_handler(
        request: web.Request,
        exception: BaseException,
    ) -> web.Response:
        if exc_cls := next(
            (_ for _ in _catch_exceptions if isinstance(exception, _)), None
        ):
            return await _exception_handlers[exc_cls](
                request=request, exception=exception
            )
        # NOTE: not in my list, return so it gets reraised
        return exception

    return _exception_handler
