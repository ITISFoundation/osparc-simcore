# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=too-many-statements
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from collections.abc import Callable

import pytest
from aiohttp import web
from models_library.rest_error import ErrorGet
from servicelib.aiohttp import status
from simcore_service_webserver.exception_handling import (
    ExceptionHandlersMap,
    HttpErrorInfo,
    exception_handling_decorator,
    to_exceptions_handlers_map,
)


@pytest.fixture
def exception_handlers_map(build_method: str) -> ExceptionHandlersMap:
    """
    Two different ways to build the exception_handlers_map
    """
    exception_handlers_map: ExceptionHandlersMap = {}

    if build_method == "custom":

        async def _value_error_as_422(
            request: web.Request, exception: BaseException
        ) -> web.Response:
            # custom exception handler
            return web.json_response(
                reason=f"{build_method=}", status=status.HTTP_422_UNPROCESSABLE_ENTITY
            )

        exception_handlers_map = {
            ValueError: _value_error_as_422,
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


@pytest.mark.parametrize("build_method", ["custom", "http_map"])
async def test_handling_exceptions_decorating_a_route(
    aiohttp_client: Callable,
    exception_handlers_map: ExceptionHandlersMap,
    build_method: str,
):

    # 1. create decorator
    exc_handling = exception_handling_decorator(exception_handlers_map)

    # adding new routes
    routes = web.RouteTableDef()

    @routes.get("/{what}")
    @exc_handling  # < ----- 2. using decorator
    async def _handler(request: web.Request):
        match request.match_info["what"]:
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

        return web.Response()

    app = web.Application()
    app.add_routes(routes)

    # 3. testing from the client side
    client = await aiohttp_client(app)

    # success
    resp = await client.get("/ok")
    assert resp.status == status.HTTP_200_OK

    # handled non-HTTPException exception
    resp = await client.get("/ValueError")
    assert resp.status == status.HTTP_422_UNPROCESSABLE_ENTITY
    if build_method == "http_map":
        body = await resp.json()
        error = ErrorGet.model_validate(body["error"])
        assert error.message == f"{build_method=}"

    # undhandled non-HTTPException
    resp = await client.get("/IndexError")
    assert resp.status == status.HTTP_500_INTERNAL_SERVER_ERROR

    # undhandled HTTPError
    resp = await client.get("/HTTPConflict")
    assert resp.status == status.HTTP_409_CONFLICT

    # undhandled HTTPSuccess
    resp = await client.get("/HTTPOk")
    assert resp.status == status.HTTP_200_OK
