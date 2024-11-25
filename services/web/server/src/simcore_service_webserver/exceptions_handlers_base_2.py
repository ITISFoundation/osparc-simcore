import functools
from collections.abc import MutableMapping
from http import HTTPStatus
from typing import Any, Protocol, TypeAlias, cast

from aiohttp import web
from servicelib.aiohttp.typing_extension import Handler
from servicelib.aiohttp.web_exceptions_extension import get_all_aiohttp_http_exceptions

# Defines exception handler as somethign that returns responses, as fastapi, and not new exceptions!
# in reality this can be reinterpreted in aiohttp since all responses can be represented as exceptions.
# Not true because fastapi.HTTPException does actually the same! Better responses because this weay we do not
# need return None or the exception itself which as we saw in the tests, it causes troubles!
#


class ExceptionHandler(Protocol):
    # Based on concept in https://www.starlette.io/exceptions/
    __name__: str

    # TODO: do not know how to define exc so that it accepts any exception!
    async def __call__(self, request: web.Request, exc: BaseException) -> web.Response:
        ...


ErrorsToHttpExceptionsMap: TypeAlias = dict[type[Exception], type[web.HTTPException]]

ExceptionHandlerRegistry: TypeAlias = dict[type[Exception], ExceptionHandler]


# injects the exceptions in a scope, e.g. an app state or some container like routes/ but to use in a module only e.g.
# as decorator or context manager?


_EXCEPTIONS_HANDLERS_KEY = f"{__name__}._EXCEPTIONS_HANDLERS_KEY"
_EXCEPTIONS_MAP_KEY = f"{__name__}._EXCEPTIONS_MAP_KEY"


def setup_exceptions_handlers(registry: MutableMapping):
    # init registry in the scope
    registry[_EXCEPTIONS_HANDLERS_KEY] = {}
    registry[_EXCEPTIONS_MAP_KEY] = {}
    # but this is very specific because it responds with only status! you migh want to have different
    # type of bodies, etc


def _get_exception_handlers(
    registry: MutableMapping,
) -> ExceptionHandlerRegistry:
    return registry.get(_EXCEPTIONS_HANDLERS_KEY, {})


def add_exception_handler(
    registry: MutableMapping,
    exc_class: type[Exception],
    handler: ExceptionHandler,
):
    """
    Registers in the scope an exception type to a handler
    """
    registry[_EXCEPTIONS_HANDLERS_KEY][exc_class] = handler


_STATUS_CODE_TO_HTTP_EXCEPTIONS: dict[
    int, type[web.HTTPException]
] = get_all_aiohttp_http_exceptions(web.HTTPException)


def _create_exception_handler_mapper(
    exc_class: type[Exception],
    http_exc_class: type[web.HTTPException],
) -> ExceptionHandler:
    error_code = f"{exc_class.__name__}"  # status_code.error_code

    async def _exception_handler(
        request: web.Request, exc: BaseException
    ) -> web.Response:
        # TODO: a better way to add error_code. TODO: create the envelope!
        assert request  # nosec
        return http_exc_class(reason=f"{exc} [{error_code}]")

    return _exception_handler


def add_exception_mapper(
    registry: MutableMapping, exception_class: type[Exception], status_code: int
):
    """
    Create an exception handlers by mapping a class to an HTTPException
    and registers it in the scope
    """
    try:
        http_exception_cls = _STATUS_CODE_TO_HTTP_EXCEPTIONS[status_code]
    except KeyError as err:
        msg = f"Invalid status code. Got {status_code=}"
        raise ValueError(msg) from err

    # adds exception handler to scope
    registry[_EXCEPTIONS_MAP_KEY][exception_class] = http_exception_cls
    add_exception_handler(
        registry,
        exception_class,
        handler=_create_exception_handler_mapper(exception_class, http_exception_cls),
    )


# ----------


async def handle_request_with_exception_handling_in_scope(
    # Create using contextlib.contextmanager
    # FIXME: !!!
    handler: Handler,
    request: web.Request,
    scope: MutableMapping[str, Any] | None = None,
) -> web.Response:
    try:
        resp = await handler(request)
        return cast(web.Response, resp)

    except Exception as exc:  # pylint: disable=broad-exception-caught
        scope = scope or request.app
        if exception_handler := _get_exception_handlers(scope).get(type(exc), None):
            resp = await exception_handler(request, exc)
        else:
            resp = web.HTTPInternalServerError()

        if isinstance(resp, web.HTTPError):
            # NOTE: this should not happen anymore! as far as I understand!?
            raise resp from exc
        return resp


# decorator
def handle_registered_exceptions(registry: MutableMapping[str, Any] | None = None):
    def _decorator(handler: Handler):
        @functools.wraps(handler)
        async def _wrapper(request: web.Request) -> web.Response:
            return await handle_request_with_exception_handling_in_scope(
                handler, request, registry
            )

        return _wrapper

    return _decorator


def openapi_error_responses(
    # If I have all the status codes mapped, I can definitively use that info to create `responses`
    # for fastapi to render the OAS preoperly
    exceptions_map: ErrorsToHttpExceptionsMap,
) -> dict[HTTPStatus, dict[str, Any]]:
    responses = {}

    for exc_class, http_exc_class in exceptions_map.items():
        status_code = HTTPStatus(http_exc_class.status_code)
        if status_code not in responses:
            responses[status_code] = {"description": f"{exc_class.__name__}"}
        else:
            responses[status_code]["description"] += f", {exc_class.__name__}"

    return responses
