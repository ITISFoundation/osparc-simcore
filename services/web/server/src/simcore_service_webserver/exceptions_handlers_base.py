import functools
import logging
from contextlib import asynccontextmanager
from typing import Protocol

from aiohttp import web
from servicelib.aiohttp.typing_extension import Handler as WebHandler

_logger = logging.getLogger(__name__)

#
# Definition
#


class WebApiExceptionHandler(Protocol):
    __name__: str

    async def __call__(
        self,
        request: web.Request,
        exception: BaseException,
    ) -> web.HTTPException | BaseException | None:
        """
        Callback to process an exception raised during a web request, allowing custom handling.

        This function can be implemented to  suppress, reraise, or transform the exception
        into an `web.HTTPException` (i.e. exceptions defined at the web-api)

        Arguments:
            request -- current request
            exception -- exception raised in web handler during this request

        Returns:
            - None: to suppress `exception`
            - `exception`: to reraise it
            - an instance of `web.HTTPException` to transform to HTTP Api exceptions (NOTE: that they can either be errors or success!)
        """


@asynccontextmanager
async def _handled_exception_context_manager(
    exception_catch: type[BaseException] | tuple[type[BaseException], ...],
    exception_handler: WebApiExceptionHandler,
    **forward_ctx,
):
    """Calls `exception_handler` on exceptions raised in this context and caught in `exception_catch`"""
    try:

        yield

    except exception_catch as e:
        exc = await exception_handler(exception=e, **forward_ctx)
        if exc:
            assert isinstance(exc, BaseException)
            raise exc from e

        _logger.debug(
            "%s suppressed %s: %s", exception_handler.__name__, type(e).__name__, f"{e}"
        )


def create_decorator_from_exception_handler(
    exception_handler: WebApiExceptionHandler,
    exception_types: type[BaseException] | tuple[type[BaseException], ...] = Exception,
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
            ):
                return await handler(request)

        return _wrapper

    return _decorator
