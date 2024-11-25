# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=too-many-statements
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import pytest
from aiohttp import web
from aiohttp.test_utils import make_mocked_request
from servicelib.aiohttp import status
from simcore_service_webserver.errors import WebServerBaseError
from simcore_service_webserver.exceptions_handlers_base_2 import (
    add_exception_handler,
    add_exception_mapper,
    handle_registered_exceptions,
    setup_exceptions_handlers,
)

# Some custom errors in my service


class BasePluginError(WebServerBaseError):
    ...


class OneError(BasePluginError):
    ...


class OtherError(BasePluginError):
    ...


@pytest.fixture
def fake_request() -> web.Request:
    return make_mocked_request("GET", "/foo")


def test_it():

    app = web.Application()

    async def my_error_handler(request: web.Request, exc: BaseException):
        assert isinstance(exc, OneError)
        return web.HTTPNotFound()

    # create register
    setup_exceptions_handlers(app)

    # register exception handler
    add_exception_handler(app, OneError, my_error_handler)

    # mapper is defined as a higher abstraction
    # that automatically produces an exception handler

    # map two exceptions?
    add_exception_mapper(app, OtherError, web.HTTPNotFound)

    # this is a handler create mapping to status_code and reason
    add_exception_mapper(app, OtherError, status.HTTP_404_NOT_FOUND)

    # NOTE: that we respond always the same way to errors, i.e. using Error model

    # shouldn't this be automatic?
    add_exception_mapper(app, web.HTTPNotFound, status.HTTP_404_NOT_FOUND)

    async def foo():
        raise OneError

    routes = web.RouteTableDef()

    @routes.get("/home")
    @handle_registered_exceptions()
    async def home(_request: web.Request):
        await foo()
        return web.HTTPOk()
