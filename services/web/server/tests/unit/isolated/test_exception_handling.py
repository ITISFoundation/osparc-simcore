# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=too-many-statements
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from collections.abc import Callable

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient
from models_library.rest_error import ErrorGet
from servicelib.aiohttp import status
from servicelib.mimetype_constants import MIMETYPE_APPLICATION_JSON, MIMETYPE_TEXT_PLAIN
from simcore_service_webserver.exception_handling import (
    ExceptionHandlersMap,
    HttpErrorInfo,
    exception_handling_decorator,
    to_exceptions_handlers_map,
)
from simcore_service_webserver.exception_handling._base import (
    exception_handling_middleware,
)
from simcore_service_webserver.exception_handling._factory import (
    create_http_error_exception_handlers_map,
)


@pytest.fixture
def exception_handlers_map(build_method: str) -> ExceptionHandlersMap:
    """
    Two different ways to build the exception_handlers_map
    """
    exception_handlers_map: ExceptionHandlersMap = {}

    if build_method == "function":

        async def _value_error_as_422_func(
            request: web.Request, exception: BaseException
        ) -> web.Response:
            # custom exception handler
            return web.json_response(
                reason=f"{build_method=}", status=status.HTTP_422_UNPROCESSABLE_ENTITY
            )

        exception_handlers_map = {
            ValueError: _value_error_as_422_func,
        }

    elif build_method == "http_map":
        exception_handlers_map = to_exceptions_handlers_map(
            {
                ValueError: HttpErrorInfo(
                    status.HTTP_422_UNPROCESSABLE_ENTITY, f"{build_method=}"
                )
            }
        )
    else:
        pytest.fail(f"Undefined {build_method=}")

    return exception_handlers_map


@pytest.mark.parametrize("build_method", ["function", "http_map"])
async def test_handling_exceptions_decorating_a_route(
    aiohttp_client: Callable,
    exception_handlers_map: ExceptionHandlersMap,
    build_method: str,
):

    # 1. create decorator
    exc_handling = exception_handling_decorator(exception_handlers_map)

    # adding new routes
    routes = web.RouteTableDef()

    @routes.post("/{what}")
    @exc_handling  # < ----- 2. using decorator
    async def _handler(request: web.Request):
        what = request.match_info["what"]
        match what:
            case "ValueError":
                raise ValueError  # handled
            case "IndexError":
                raise IndexError  # not-handled
            case "HTTPConflict":
                raise web.HTTPConflict  # not-handled
            case "HTTPOk":
                # non errors should NOT be raised,
                # SEE https://github.com/ITISFoundation/osparc-simcore/pull/6829
                # but if it is so ...
                raise web.HTTPOk  # not-handled

        return web.Response(text=what)

    app = web.Application()
    app.add_routes(routes)

    # 3. testing from the client side
    client: TestClient = await aiohttp_client(app)

    # success
    resp = await client.post("/ok")
    assert resp.status == status.HTTP_200_OK

    # handled non-HTTPException exception
    resp = await client.post("/ValueError")
    assert resp.status == status.HTTP_422_UNPROCESSABLE_ENTITY
    if build_method == "http_map":
        body = await resp.json()
        error = ErrorGet.model_validate(body["error"])
        assert error.message == f"{build_method=}"

    # undhandled non-HTTPException
    resp = await client.post("/IndexError")
    assert resp.status == status.HTTP_500_INTERNAL_SERVER_ERROR

    # undhandled HTTPError
    resp = await client.post("/HTTPConflict")
    assert resp.status == status.HTTP_409_CONFLICT

    # undhandled HTTPSuccess
    resp = await client.post("/HTTPOk")
    assert resp.status == status.HTTP_200_OK


@pytest.mark.parametrize("build_method", ["function", "http_map"])
async def test_handling_exceptions_with_middelware(
    aiohttp_client: Callable,
    exception_handlers_map: ExceptionHandlersMap,
    build_method: str,
):
    routes = web.RouteTableDef()

    @routes.post("/{what}")  # NO decorantor now
    async def _handler(request: web.Request):
        match request.match_info["what"]:
            case "ValueError":
                raise ValueError  # handled
        return web.Response()

    app = web.Application()
    app.add_routes(routes)

    # 1. create & install middleware
    exc_handling = exception_handling_middleware(exception_handlers_map)
    app.middlewares.append(exc_handling)

    # 2. testing from the client side
    client: TestClient = await aiohttp_client(app)

    # success
    resp = await client.post("/ok")
    assert resp.status == status.HTTP_200_OK

    # handled non-HTTPException exception
    resp = await client.post("/ValueError")
    assert resp.status == status.HTTP_422_UNPROCESSABLE_ENTITY
    if build_method == "http_map":
        body = await resp.json()
        error = ErrorGet.model_validate(body["error"])
        assert error.message == f"{build_method=}"


@pytest.mark.parametrize("with_middleware", [True, False])
async def test_raising_aiohttp_http_errors(
    aiohttp_client: Callable, with_middleware: bool
):
    routes = web.RouteTableDef()

    @routes.post("/raise-http-error")
    async def _handler1(request: web.Request):
        # 1. raises aiohttp.web_exceptions.HttpError
        raise web.HTTPConflict

    app = web.Application()
    app.add_routes(routes)

    # 2. create & install middleware handlers for ALL http (optional)
    if with_middleware:
        exc_handling = exception_handling_middleware(
            exception_handlers_map=create_http_error_exception_handlers_map()
        )
        app.middlewares.append(exc_handling)

    # 3. testing from the client side
    client: TestClient = await aiohttp_client(app)

    resp = await client.post("/raise-http-error")
    assert resp.status == status.HTTP_409_CONFLICT

    if with_middleware:
        assert resp.content_type == MIMETYPE_APPLICATION_JSON
        ErrorGet.model_construct((await resp.json())["error"])
    else:
        # default
        assert resp.content_type == MIMETYPE_TEXT_PLAIN
