# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=too-many-statements
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import logging

import pytest
from aiohttp import web
from aiohttp.test_utils import make_mocked_request
from servicelib.aiohttp import status
from simcore_service_webserver.errors import WebServerBaseError
from simcore_service_webserver.exceptions_handlers import (
    HttpErrorInfo,
    create_decorator_from_exception_handler,
)
from simcore_service_webserver.exceptions_handlers_base import (
    _handled_exception_context_manager,
)
from simcore_service_webserver.exceptions_handlers_base_2 import (
    add_exception_handler,
    add_exception_mapper,
    handle_registered_exceptions,
    setup_exception_handlers,
)
from simcore_service_webserver.exceptions_handlers_http_error_map import (
    _sort_exceptions_by_specificity,
    create_exception_handler_from_http_error_map,
)

# Some custom errors in my service


class BasePluginError(WebServerBaseError):
    ...


class OneError(BasePluginError):
    ...


class OtherError(BasePluginError):
    ...


def test_sort_concrete_first():
    assert _sort_exceptions_by_specificity([Exception, BasePluginError]) == [
        BasePluginError,
        Exception,
    ]

    assert _sort_exceptions_by_specificity(
        [Exception, BasePluginError], concrete_first=False
    ) == [
        Exception,
        BasePluginError,
    ]


def test_sort_exceptions_by_specificity():

    got_exceptions_cls = _sort_exceptions_by_specificity(
        [
            Exception,
            OtherError,
            OneError,
            BasePluginError,
            ValueError,
            ArithmeticError,
            ZeroDivisionError,
        ]
    )

    for from_, exc in enumerate(got_exceptions_cls, start=1):
        for exc_after in got_exceptions_cls[from_:]:
            assert not issubclass(exc_after, exc), f"{got_exceptions_cls=}"


@pytest.fixture
def fake_request() -> web.Request:
    return make_mocked_request("GET", "/foo")


def test_create_exception_handler_from_http_error_map(fake_request: web.Request):

    # call exception handler factory
    exc_handler = create_exception_handler_from_http_error_map(
        {
            OneError: HttpErrorInfo(
                status.HTTP_400_BAD_REQUEST, "Error One mapped to 400"
            )
        }
    )

    # Converts exception in map
    got_exc = exc_handler(OneError(), fake_request)

    assert isinstance(got_exc, web.HTTPBadRequest)
    assert got_exc.reason == "Error One mapped to 400"

    # By-passes exceptions not listed
    err = RuntimeError()
    assert exc_handler(err, fake_request) is err


def test__handled_exception_context_manager(fake_request: web.Request):
    def _suppress_handler(exception, request):
        assert request == fake_request
        assert isinstance(
            exception, BasePluginError
        ), "only BasePluginError exceptions should call this handler"
        return None  # noqa: RET501, PLR1711

    def _fun(raises):
        with _handled_exception_context_manager(
            BasePluginError, _suppress_handler, request=fake_request
        ):
            raise raises

    # checks
    _fun(raises=OneError)
    _fun(raises=OtherError)

    with pytest.raises(ArithmeticError):
        _fun(raises=ArithmeticError)


async def test_create_decorator_from_exception_handler(
    caplog: pytest.LogCaptureFixture,
):

    exc_handler = create_exception_handler_from_http_error_map(
        {
            OneError: HttpErrorInfo(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                "Human readable error transmitted to the front-end",
            )
        }
    )

    _handle_exceptions = create_decorator_from_exception_handler(
        exception_handler=exc_handler,
        exception_types=BasePluginError,  # <--- FIXME" this is redundant because exception has been already passed in exc_handler!
    )

    @_handle_exceptions
    async def _rest_handler(request: web.Request) -> web.Response:
        if request.query.get("raise") == "OneError":
            raise OneError
        if request.query.get("raise") == "ArithmeticError":
            raise ArithmeticError

        return web.Response(reason="all good")

    with caplog.at_level(logging.ERROR):

        # emulates successful call
        resp = await _rest_handler(make_mocked_request("GET", "/foo"))
        assert resp.status == status.HTTP_200_OK
        assert resp.reason == "all good"

        assert not caplog.records

        # this will be passed and catched by the outermost error middleware
        with pytest.raises(ArithmeticError):
            await _rest_handler(
                make_mocked_request("GET", "/foo?raise=ArithmeticError")
            )

        assert not caplog.records

        # this is a 5XX will be converted to response but is logged as error as well
        with pytest.raises(web.HTTPException) as exc_info:
            await _rest_handler(make_mocked_request("GET", "/foo?raise=OneError"))

        resp = exc_info.value
        assert resp.status == status.HTTP_503_SERVICE_UNAVAILABLE
        assert "front-end" in resp.reason

        assert caplog.records
        assert caplog.records[0].levelno == logging.ERROR
    # typically capture by last
    with pytest.raises(ArithmeticError):
        resp = await _rest_handler(
            make_mocked_request("GET", "/foo?raise=ArithmeticError")
        )


def test_it():
    class MyException(Exception):
        ...

    class OtherException(Exception):
        ...

    app = web.Application()

    async def my_error_handler(request: web.Request, exc: MyException):
        return web.HTTPNotFound()

    # define at the app level
    setup_exception_handlers(app)
    add_exception_handler(app, MyException, my_error_handler)
    add_exception_mapper(app, OtherException, web.HTTPNotFound)

    async def foo():
        raise MyException

    routes = web.RouteTableDef()

    @routes.get("/home")
    @handle_registered_exceptions()
    async def home(_request: web.Request):
        await foo()
        return web.HTTPOk()
