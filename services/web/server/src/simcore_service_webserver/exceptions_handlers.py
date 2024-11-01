import functools
import logging
from collections.abc import Awaitable, Callable, MutableMapping
from contextlib import contextmanager
from http import HTTPStatus
from typing import Any, NamedTuple, Protocol, TypeAlias, cast

from aiohttp import web
from servicelib.aiohttp.typing_extension import Handler
from servicelib.aiohttp.web_exceptions_extension import get_all_aiohttp_http_exceptions
from servicelib.logging_errors import create_troubleshotting_log_kwargs
from servicelib.status_codes_utils import is_5xx_server_error

_logger = logging.getLogger(__name__)

#
# Definition
#


class WebApiExceptionHandler(Protocol):
    def __call__(
        self, exception: BaseException, request: web.Request
    ) -> web.HTTPException | BaseException | None:
        """
        Callback to process an exception raised during a web request, allowing custom handling.

        This function can be implemented to  suppress, reraise, or transform the exception
        into an `web.HTTPException` (i.e. exceptions defined at the web-api)

        Arguments:
            exception -- exception raised in web handler during this request
            request -- current request

        Returns:
            - None: to suppress `exception`
            - `exception`: to reraise it
            - an instance of `web.HTTPException` to transform to HTTP Api exceptions (NOTE: that they can either be errors or success!)
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
    Factory to create decorators that wraps exceptions on api-handler functions
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
# CUSTOM EXCEPTIONS HANDLERS
#


class _DefaultDict(dict):
    def __missing__(self, key):
        return f"'{key}=?'"


_STATUS_CODE_TO_HTTP_EXCEPTIONS: dict[
    int, type[web.HTTPException]
] = get_all_aiohttp_http_exceptions(web.HTTPException)


def make_handler_exception_to_status_code(
    exception_cls: type[BaseException], status_code: int, user_msg_template: str
) -> WebApiExceptionHandler:
    """
    Creates a custom `WebApiExceptionHandler` that maps specific exception to an http status code error

    Given an `ExceptionToHttpErrorMap`, this function returns a handler that checks if an exception
    matches one in the map, returning an HTTP error with the mapped status code and message.
    Server errors (5xx) include additional logging with request context. Unmapped exceptions are
    returned as-is for re-raising.

    Arguments:
        exception_cls: exception raise during the request
        status_code: the http status code to associate at the web-api interface to this error
        user_msg_template: a template string to pass to the HttpError

    Returns:
        A web api exception handler
    """

    def _exception_handler(
        exception: BaseException,
        request: web.Request,
    ) -> web.HTTPException | BaseException | None:
        assert isinstance(exception, exception_cls)  # nosec

        # safe formatting, i.e. does not raise
        user_msg = user_msg_template.format_map(
            _DefaultDict(getattr(exception, "__dict__", {}))
        )

        http_error_cls = _STATUS_CODE_TO_HTTP_EXCEPTIONS[status_code]
        assert http_error_cls  # nosec

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
        return http_error_cls(reason=user_msg)

    return _exception_handler


class HttpErrorInfo(NamedTuple):
    status_code: int
    msg_template: str


ExceptionToHttpErrorMap: TypeAlias = dict[type[BaseException], HttpErrorInfo]


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

    _exception_handlers = {
        exc_cls: make_handler_exception_to_status_code(
            exception_cls=exc_cls,
            status_code=http_error_info.status_code,
            user_msg_template=http_error_info.msg_template,
        )
        for exc_cls, http_error_info in to_http_error_map.items()
    }

    _catch_exceptions = _sort_exceptions_by_specificity(
        list(_exception_handlers.keys())
    )

    def _exception_handler(
        exception: BaseException,
        request: web.Request,
    ) -> web.HTTPError | BaseException | None:
        if exc_cls := next(
            (_ for _ in _catch_exceptions if isinstance(exception, _)), None
        ):
            return _exception_handlers[exc_cls](request=request, exception=exception)
        # NOTE: not in my list, return so it gets reraised
        return exception

    return _exception_handler


# OLD VERSION OF IT with really good ideas ! --------------------


#
# Defines exception handler as somethign that returns responses, as fastapi, and not new exceptions!
# in reality this can be reinterpreted in aiohttp since all responses can be represented as exceptions.
# Not true because fastapi.HTTPException does actually the same! Better responses because this weay we do not
# need return None or the exception itself which as we saw in the tests, it causes troubles!
#

ExceptionHandler: TypeAlias = Callable[
    [web.Request, Exception], Awaitable[web.Response]
]

ExceptionsMap: TypeAlias = dict[type[Exception], type[web.HTTPException]]

ExceptionHandlerRegistry: TypeAlias = dict[type[Exception], ExceptionHandler]


# injects the exceptions in a scope, e.g. an app state or some container like routes/ but to use in a module only e.g.
# as decorator or context manager?


def setup_exception_handlers(scope: MutableMapping[str, Any]):
    scope["exceptions_handlers"] = {}
    scope["exceptions_map"] = {}
    # but this is very specific because it responds with only status! you migh want to have different
    # type of bodies, etc


def _get_exception_handler_registry(
    scope: MutableMapping[str, Any]
) -> ExceptionHandlerRegistry:
    return scope.get("exceptions_handlers", {})


def add_exception_handler(
    scope: MutableMapping[str, Any],
    exc_class: type[Exception],
    handler: ExceptionHandler,
):
    scope["exceptions_handlers"][exc_class] = handler


def _create_exception_handler_mapper(
    exc_class: type[Exception],
    http_exc_class: type[web.HTTPException],
) -> ExceptionHandler:
    error_code = f"{exc_class.__name__}"  # status_code.error_code

    async def _exception_handler(_: web.Request, exc: Exception) -> web.Response:
        # TODO: a better way to add error_code. TODO: create the envelope!
        return http_exc_class(reason=f"{exc} [{error_code}]")

    return _exception_handler


def add_exception_mapper(
    scope: MutableMapping[str, Any],
    exc_class: type[Exception],
    http_exc_class: type[web.HTTPException],
):
    # adds exception handler to scope
    scope["exceptions_map"][exc_class] = http_exc_class
    add_exception_handler(
        scope,
        exc_class,
        handler=_create_exception_handler_mapper(exc_class, http_exc_class),
    )


async def handle_request_with_exception_handling_in_scope(
    handler: Handler,
    request: web.Request,
    scope: MutableMapping[str, Any] | None = None,
) -> web.Response:
    try:
        resp = await handler(request)
        return cast(web.Response, resp)

    except Exception as exc:  # pylint: disable=broad-exception-caught
        scope = scope or request.app
        if exception_handler := _get_exception_handler_registry(scope).get(
            type(exc), None
        ):
            resp = await exception_handler(request, exc)
        else:
            resp = web.HTTPInternalServerError()

        if isinstance(resp, web.HTTPError):
            # NOTE: this should not happen anymore! as far as I understand!?
            raise resp from exc
        return resp


def handle_registered_exceptions(scope: MutableMapping[str, Any] | None = None):
    def _decorator(handler: Handler):
        @functools.wraps(handler)
        async def _wrapper(request: web.Request) -> web.Response:
            return await handle_request_with_exception_handling_in_scope(
                handler, request, scope
            )

        return _wrapper

    return _decorator


# If I have all the status codes mapped, I can definitively use that info to create `responses`
# for fastapi to render the OAS preoperly
def openapi_error_responses(
    exceptions_map: ExceptionsMap,
) -> dict[HTTPStatus, dict[str, Any]]:
    responses = {}

    for exc_class, http_exc_class in exceptions_map.items():
        status_code = HTTPStatus(http_exc_class.status_code)
        if status_code not in responses:
            responses[status_code] = {"description": f"{exc_class.__name__}"}
        else:
            responses[status_code]["description"] += f", {exc_class.__name__}"

    return responses
