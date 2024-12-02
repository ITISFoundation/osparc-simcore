import functools
import logging
from collections.abc import Callable, Iterable
from contextlib import AbstractAsyncContextManager
from types import TracebackType
from typing import Protocol, TypeAlias

from aiohttp import web
from servicelib.aiohttp.typing_extension import Handler as WebHandler
from servicelib.aiohttp.typing_extension import Middleware as WebMiddleware

_logger = logging.getLogger(__name__)


class AiohttpExceptionHandler(Protocol):
    __name__: str

    async def __call__(
        self,
        request: web.Request,
        exception: Exception,
    ) -> web.StreamResponse:
        """
        Callback that handles an exception produced during a request and transforms it into a response

        Arguments:
            request -- current request
            exception -- exception raised in web handler during this request
        """


ExceptionHandlersMap: TypeAlias = dict[type[Exception], AiohttpExceptionHandler]


def _sort_exceptions_by_specificity(
    exceptions: Iterable[type[Exception]], *, concrete_first: bool = True
) -> list[type[Exception]]:
    """
    Keyword Arguments:
        concrete_first -- If True, concrete subclasses precede their superclass (default: {True}).
    """
    return sorted(
        exceptions,
        key=lambda exc: sum(issubclass(e, exc) for e in exceptions if e is not exc),
        reverse=not concrete_first,
    )


class ExceptionHandlingContextManager(AbstractAsyncContextManager):
    """
    A dynamic try-except context manager for handling exceptions in web handlers.
    Maps exception types to corresponding handlers, allowing structured error management, i.e.
    essentially something like
    ```
        try:

            resp = await handler(request)

        except exc_type1 as exc1:
            resp = await exc_handler1(request)
        except exc_type2 as exc1:
            resp = await exc_handler2(request)
        # etc

    ```
    and `exception_handlers_map` defines the mapping of exception types (`exc_type*`) to their handlers (`exc_handler*`).
    """

    def __init__(
        self,
        exception_handlers_map: ExceptionHandlersMap,
        *,
        request: web.Request,
    ):
        self._exc_handlers_map = exception_handlers_map
        self._exc_types_by_specificity = _sort_exceptions_by_specificity(
            list(self._exc_handlers_map.keys()), concrete_first=True
        )
        self._request: web.Request = request
        self._response: web.StreamResponse | None = None

    def _get_exc_handler_or_none(
        self, exc_type: type[Exception], exc_value: Exception
    ) -> AiohttpExceptionHandler | None:
        exc_handler = self._exc_handlers_map.get(exc_type)
        if not exc_handler and (
            base_exc_type := next(
                (
                    _type
                    for _type in self._exc_types_by_specificity
                    if isinstance(exc_value, _type)
                ),
                None,
            )
        ):
            exc_handler = self._exc_handlers_map[base_exc_type]
        return exc_handler

    async def __aenter__(self):
        self._response = None
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool:
        if (
            exc_value is not None
            and exc_type is not None
            and isinstance(exc_value, Exception)
            and issubclass(exc_type, Exception)
            and (exc_handler := self._get_exc_handler_or_none(exc_type, exc_value))
        ):
            self._response = await exc_handler(
                request=self._request, exception=exc_value
            )
            return True  # suppress
        return False  # reraise

    def get_response_or_none(self) -> web.StreamResponse | None:
        """
        Returns the response generated by the exception handler, if an exception was handled. Otherwise None
        """
        return self._response


def exception_handling_decorator(
    exception_handlers_map: dict[type[Exception], AiohttpExceptionHandler]
) -> Callable[[WebHandler], WebHandler]:
    """Creates a decorator to manage exceptions raised in a given route handler.
    Ensures consistent exception management across decorated handlers.

    SEE examples test_exception_handling
    """

    def _decorator(handler: WebHandler):
        @functools.wraps(handler)
        async def _wrapper(request: web.Request) -> web.StreamResponse:
            cm = ExceptionHandlingContextManager(
                exception_handlers_map, request=request
            )
            async with cm:
                return await handler(request)

            # If an exception was handled, return the exception handler's return value
            response = cm.get_response_or_none()
            assert response is not None  # nosec
            return response

        return _wrapper

    return _decorator


def exception_handling_middleware(
    exception_handlers_map: dict[type[Exception], AiohttpExceptionHandler]
) -> WebMiddleware:
    """Constructs middleware to handle exceptions raised across app routes

    SEE examples test_exception_handling
    """
    _handle_excs = exception_handling_decorator(
        exception_handlers_map=exception_handlers_map
    )

    @web.middleware
    async def middleware_handler(request: web.Request, handler: WebHandler):
        return await _handle_excs(handler)(request)

    return middleware_handler
