import functools
import logging
from collections.abc import Callable
from contextlib import contextmanager
from typing import NamedTuple, Protocol, TypeAlias

from aiohttp import web
from servicelib.aiohttp.typing_extension import Handler
from servicelib.aiohttp.web_exceptions_extension import get_http_error_class_or_none
from servicelib.logging_errors import create_troubleshotting_log_kwargs
from servicelib.status_codes_utils import is_5xx_server_error

_logger = logging.getLogger(__name__)


class WebApiExceptionHandler(Protocol):
    def __call__(
        self, request: web.Request, exception: BaseException
    ) -> web.HTTPError | BaseException | None:
        """Callable to handle an `exception` raised during `request`

        Provides a way to handle or transform exceptions raised during a request
        (coming from lower API) into http errors (at web-API)

        Arguments:
            request -- current request
            exception -- exception raised in web handler during this request

        Returns:
            - None: to suppress `exception`
            - `exception`: to reraise it
            - an instance of `web.HTTPError` to transform to HTTP Api exceptions
        """


@contextmanager
def _handled_exception_context(
    exception_catch: type[BaseException] | tuple[type[BaseException], ...],
    exception_handler: Callable,
    **forward_ctx,
):
    try:
        yield
    except exception_catch as e:
        if exc := exception_handler(e, **forward_ctx):
            assert isinstance(exc, BaseException)
            raise exc from e

        _logger.debug(
            "%s suppressed %s: %s", exception_handler.__name__, type(e).__name__, f"{e}"
        )


def create_exception_handlers_decorator(
    exception_handler: WebApiExceptionHandler,
    exception_types: type[BaseException] | tuple[type[BaseException], ...] = Exception,
):
    """
    Creates a function to decorate routes handlers functions
    that can catch and handle exceptions raised in the decorated functions
    """

    def _decorator(handler: Handler):
        @functools.wraps(handler)
        async def _wrapper(request: web.Request) -> web.StreamResponse:
            # NOTE: this could als be dynamically extended with other
            #  customizations of error handlers [(exception_types,exception_handler ), ...]
            #  then we can use contextlib.ExitStack() to nest them.
            #  In that case, the order will be important
            with _handled_exception_context(
                exception_types,
                exception_handler,
                request=request,
            ):
                return await handler(request)

        return _wrapper

    return _decorator


#
# Customizations
#


class HttpErrorInfo(NamedTuple):
    status_code: int
    msg_template: str


ExceptionToHttpErrorMap: TypeAlias = dict[type[BaseException], HttpErrorInfo]


class _DefaultDict(dict):
    def __missing__(self, key):
        return f"'{key}=?'"


def _sort_exceptions_by_specificity(
    exceptions: list[type[BaseException]],
) -> list[type[BaseException]]:
    return sorted(
        exceptions,
        key=lambda exc: sum(issubclass(e, exc) for e in exceptions if e is not exc),
        reverse=True,
    )


def create__http_error_map_handler(
    to_http_error_map: ExceptionToHttpErrorMap,
) -> WebApiExceptionHandler:
    """Factor to implement a customization of WebApiExceptionHandler

    ExceptionToHttpErrorMap:  maps exceptions to an http status code and message
    """
    included: list[type[BaseException]] = _sort_exceptions_by_specificity(
        list(to_http_error_map.keys())
    )

    def _handler(
        request: web.Request,
        exception: BaseException,
    ) -> web.HTTPError | BaseException | None:
        if exc_cls := next((_ for _ in included if isinstance(exception, _)), None):
            http_error_info = to_http_error_map[exc_cls]

            # safe formatting, i.e. does not raise
            user_msg = http_error_info.msg_template.format_map(
                _DefaultDict(getattr(exception, "__dict__", {}))
            )

            http_error_cls = get_http_error_class_or_none(http_error_info.status_code)
            assert http_error_cls  # nosec

            if is_5xx_server_error(http_error_info.status_code):
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
            return http_error_cls(reason=user_msg)
        return exception

    return _handler
