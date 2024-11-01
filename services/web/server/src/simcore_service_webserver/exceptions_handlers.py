import functools
import logging
from collections.abc import Iterable
from typing import NamedTuple, TypeAlias
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
        self, exception: BaseException, request: web.Request
    ) -> web.HTTPError | BaseException | None:
        """
        Callback to process an exception raised during a web request, allowing custom handling.

        This function can be implemented to  suppress, reraise, or transform the exception
        into an `web.HTTPError` (i.e.the errors specified in the web-api)

        Arguments:
            exception -- exception raised in web handler during this request
            request -- current request

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
            with _handled_exception_context(
                exception_types,
                exception_handler,
                request=request,
            ):
                return await handler(request)

        return _wrapper

    return _decorator


#
# Http Error Map Handler Customization
#


class HttpErrorInfo(NamedTuple):
    status_code: int
    msg_template: str


ExceptionToHttpErrorMap: TypeAlias = dict[type[BaseException], HttpErrorInfo]


class _DefaultDict(dict):
    def __missing__(self, key):
        return f"'{key}=?'"


def _sort_exceptions_by_specificity(
    exceptions: Iterable[type[BaseException]], *, concrete_first: bool = True
) -> list[type[BaseException]]:
    return sorted(
        exceptions,
        key=lambda exc: sum(issubclass(e, exc) for e in exceptions if e is not exc),
        reverse=not concrete_first,
    )


def create_exception_handlers_decorator(
    exceptions_catch: type[BaseException] | tuple[type[BaseException], ...],
    exc_to_status_map: ExceptionToHttpErrorMap,
):
    mapped_classes: tuple[type[BaseException], ...] = tuple(
        _sort_exceptions_by_specificity(exc_to_status_map.keys())
    )

    assert all(  # nosec
        issubclass(cls, exceptions_catch) for cls in mapped_classes
    ), f"Every {mapped_classes=} must inherit by one or more of {exceptions_catch=}"

    def _decorator(handler: Handler):
        @functools.wraps(handler)
        async def _wrapper(request: web.Request) -> web.StreamResponse:
            try:
                return await handler(request)

            except exceptions_catch as exc:
                if exc_cls := next(
                    (cls for cls in mapped_classes if isinstance(exc, cls)), None
                ):
                    http_error_info = exc_to_status_map[exc_cls]

                    # safe formatting, i.e. does not raise
                    user_msg = http_error_info.msg_template.format_map(
                        _DefaultDict(getattr(exc, "__dict__", {}))
                    )

                    http_error_cls = get_http_error_class_or_none(
                        http_error_info.status_code
                    )
                    assert http_error_cls  # nosec

                    if is_5xx_server_error(http_error_info.status_code):
                        _logger.exception(
                            **create_troubleshotting_log_kwargs(
                                user_msg,
                                error=exc,
                                error_context={
                                    "request": request,
                                    "request.remote": f"{request.remote}",
                                    "request.method": f"{request.method}",
                                    "request.path": f"{request.path}",
                                },
                            )
                        )
                    raise http_error_cls(reason=user_msg) from exc
                raise  # reraise

        return _wrapper

    return _decorator
def create__http_error_map_handler(
    to_http_error_map: ExceptionToHttpErrorMap,
) -> WebApiExceptionHandler:
    """
    Creates a custom `WebApiExceptionHandler` that maps specific exceptions to HTTP errors.

    Given an `ExceptionToHttpErrorMap`, this function returns a handler that checks if an exception
    matches one in the map, returning an HTTP error with the mapped status code and message.
    Server errors (5xx) include additional logging with request context. Unmapped exceptions are
    returned as-is for re-raising.

    Arguments:
        to_http_error_map -- Maps exceptions to HTTP status codes and messages.

    Returns:
        A web api exception handler
    """
    included: list[type[BaseException]] = _sort_exceptions_by_specificity(
        list(to_http_error_map.keys())
    )

    def _handler(
        exception: BaseException,
        request: web.Request,
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
        # NOTE: not in my list, return so it gets reraised
        return exception

    return _handler
