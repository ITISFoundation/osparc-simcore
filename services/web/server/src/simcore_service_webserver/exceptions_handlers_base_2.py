import functools
import logging
from collections.abc import Awaitable, Callable, MutableMapping
from http import HTTPStatus
from typing import Any, TypeAlias, cast

from aiohttp import web

_logger = logging.getLogger(__name__)


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
