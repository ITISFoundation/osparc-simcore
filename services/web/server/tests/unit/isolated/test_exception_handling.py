# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=too-many-statements
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from collections.abc import Callable

from aiohttp import web
from servicelib.aiohttp import status
from simcore_service_webserver.exception_handling import exception_handling_decorator


async def test_handling_exceptions_decorating_a_route(aiohttp_client: Callable):

    # custom exception handler
    async def value_error_as_422(
        request: web.Request, exception: BaseException
    ) -> web.Response:
        return web.json_response(status=status.HTTP_422_UNPROCESSABLE_ENTITY)

    # decorator
    exc_handling = exception_handling_decorator({ValueError: value_error_as_422})

    # adding new routes
    routes = web.RouteTableDef()

    @routes.get("/{what}")
    @exc_handling  # < ----- using decorator
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

    # testing from the client side
    client = await aiohttp_client(app)

    # success
    resp = await client.get("/ok")
    assert resp.status == status.HTTP_200_OK

    # handled non-HTTPException exception
    resp = await client.get("/ValueError")
    assert resp.status == status.HTTP_422_UNPROCESSABLE_ENTITY

    # undhandled non-HTTPException
    resp = await client.get("/IndexError")
    assert resp.status == status.HTTP_500_INTERNAL_SERVER_ERROR

    # undhandled HTTPError
    resp = await client.get("/HTTPConflict")
    assert resp.status == status.HTTP_409_CONFLICT

    # undhandled HTTPSuccess
    resp = await client.get("/HTTPOk")
    assert resp.status == status.HTTP_200_OK
