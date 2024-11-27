import functools
import logging
from collections.abc import Iterable
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
        exception: BaseException,
    ) -> web.Response:
        """
        Callback that handles an exception produced during a request and transforms it into a response

        Arguments:
            request -- current request
            exception -- exception raised in web handler during this request
        """
        ...  # pylint: disable=unnecessary-ellipsis


ExceptionHandlersMap: TypeAlias = dict[type[BaseException], AiohttpExceptionHandler]


def _sort_exceptions_by_specificity(
    exceptions: Iterable[type[BaseException]], *, concrete_first: bool = True
) -> list[type[BaseException]]:
    return sorted(
        exceptions,
        key=lambda exc: sum(issubclass(e, exc) for e in exceptions if e is not exc),
        reverse=not concrete_first,
    )


class ExceptionHandlingContextManager(AbstractAsyncContextManager):
    """Essentially a dynamic try-except context manager to
    handle exceptions raised by a web handler, i.e.
    ```
        try:

            resp = await handler(request)

        except exc_type1 as exc1:
            resp = await exc_handler1(request)
        except exc_type2 as exc1:
            resp = await exc_handler2(request)

        # and so on ... as in `exception_handlers_map[exc_type] == exc_handler`
    ```

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
        self._response: web.Response | None = None

    def _get_exc_handler_or_none(
        self, exc_type: type[BaseException], exc_value: BaseException
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
            and (exc_handler := self._get_exc_handler_or_none(exc_type, exc_value))
        ):
            self._response = await exc_handler(
                request=self._request, exception=exc_value
            )
            return True  # suppress
        return False  # reraise

    def get_response(self) -> web.Response | None:
        return self._response


def exception_handling_decorator(
    exception_handlers_map: dict[type[BaseException], AiohttpExceptionHandler]
):
    """Creates a decorator to handle all registered exceptions raised in a given route handler

    SEE usage example in test_exception_handling
    """

    def _decorator(handler: WebHandler):
        @functools.wraps(handler)
        async def _wrapper(request: web.Request):
            cm = ExceptionHandlingContextManager(
                exception_handlers_map, request=request
            )
            async with cm:
                return await handler(request)

            # If an exception was handled, return the exception handler's return value
            response = cm.get_response()
            assert response is not None  # nosec
            return response

        return _wrapper

    return _decorator


def exception_handling_middleware(
    exception_handlers_map: dict[type[BaseException], AiohttpExceptionHandler]
) -> WebMiddleware:
    """
    Creates a middleware to handle all registered exceptions raised in any app's route
    """
    _handle_excs = exception_handling_decorator(
        exception_handlers_map=exception_handlers_map
    )

    @web.middleware
    async def middleware_handler(request: web.Request, handler: WebHandler):
        return await _handle_excs(handler)(request)

    return middleware_handler
