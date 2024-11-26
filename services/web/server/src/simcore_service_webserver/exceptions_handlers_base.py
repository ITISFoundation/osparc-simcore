import functools
import logging
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import AsyncIterator, Protocol

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
        Callback to process an exception raised during a web request, allowing custom handling.

        This function can be implemented to  suppress, (transform &) reraise as web.HTTPError
        or return a web.Response

        Arguments:
            request -- current request
            exception -- exception raised in web handler during this request
        """
        ...  # pylint: disable=unnecessary-ellipsis


@dataclass
class _ExceptionContext:
    response: web.Response | None = None


@asynccontextmanager
async def _handled_exception_context_manager(
    exception_catch: type[BaseException] | tuple[type[BaseException], ...],
    exception_handler: AiohttpExceptionHandler,
    **forward_ctx,
) -> AsyncIterator[_ExceptionContext]:
    """
    Calls `exception_handler` on exceptions raised in this context and caught in `exception_catch`
    """
    ctx = _ExceptionContext()
    try:

        yield ctx

    except exception_catch as e:
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
