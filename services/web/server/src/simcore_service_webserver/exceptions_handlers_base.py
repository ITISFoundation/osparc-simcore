import functools
import logging
from collections.abc import AsyncIterator, Iterable
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from dataclasses import dataclass
from types import TracebackType
from typing import Protocol

from aiohttp import web
from servicelib.aiohttp.typing_extension import Handler as WebHandler

_logger = logging.getLogger(__name__)

#
# Definition
#


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


def _sort_exceptions_by_specificity(
    exceptions: Iterable[type[BaseException]], *, concrete_first: bool = True
) -> list[type[BaseException]]:
    return sorted(
        exceptions,
        key=lambda exc: sum(issubclass(e, exc) for e in exceptions if e is not exc),
        reverse=not concrete_first,
    )


class AsyncDynamicTryExceptContext(AbstractAsyncContextManager):
    """Context manager to handle exceptions if they match any in the exception_handlers dictionary"""

    def __init__(
        self,
        exception_handlers: dict[type[BaseException], AiohttpExceptionHandler],
        *,
        request: web.Request,
    ):
        self.exception_handlers = exception_handlers
        self.request = request
        self.response = None

    async def __aenter__(self):
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool:
        # FIXME: the specificity is not resolved by the __aexit__ caller
        if exc_type is not None and exc_type in self.exception_handlers:
            assert exc_value  # nosec

            exc_handler = self.exception_handlers[exc_type]
            self.response = await exc_handler(request=self.request, exception=exc_value)
            return True  # suppress
        return False  # reraise

    def get_response(self):
        return self.response


def async_try_except_decorator(
    exception_handlers: dict[type[BaseException], AiohttpExceptionHandler]
):
    def _decorator(handler: WebHandler):
        @functools.wraps(handler)
        async def _wrapper(request: web.Request) -> web.StreamResponse:
            cm = AsyncDynamicTryExceptContext(exception_handlers, request=request)
            async with cm:
                return await handler(request)

            # If an exception was handled, return the exception handler's return value
            response = cm.get_response()
            assert response is not None  # nosec
            return response

        return _wrapper

    return _decorator


# ----------------


@dataclass
class _ExceptionContext:
    response: web.Response | None = None


@asynccontextmanager
async def _handled_exception_context_manager(
    exception_types: type[BaseException] | tuple[type[BaseException], ...],
    exception_handler: AiohttpExceptionHandler,
    **forward_ctx,
) -> AsyncIterator[_ExceptionContext]:
    """
    Calls `exception_handler` on exceptions raised in this context and caught in `exception_catch`
    """
    ctx = _ExceptionContext()
    try:

        yield ctx

    except exception_types as e:
        # NOTE: exception_types are automatically sorted by specififyt
        response = await exception_handler(exception=e, **forward_ctx)
        assert isinstance(response, web.Response)  # nosec
        ctx.response = response


def create_decorator_from_exception_handler(
    exception_types: type[BaseException] | tuple[type[BaseException], ...],
    exception_handler: AiohttpExceptionHandler,
):
    """Returns a decorator for aiohttp's web.Handler functions

    Builds a decorator function that applies _handled_exception_context to an aiohttp Handler
    """

    def _decorator(handler: WebHandler):
        @functools.wraps(handler)
        async def _wrapper(request: web.Request) -> web.StreamResponse:

            async with _handled_exception_context_manager(
                exception_types,
                exception_handler,
                request=request,
            ) as exc_ctx:

                return await handler(request)

            return exc_ctx.response

        return _wrapper

    return _decorator
