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
from simcore_service_webserver.exceptions_handlers import (
    HttpErrorInfo,
    _handled_exception_context,
    _sort_exceptions_by_specificity,
    create__http_error_map_handler,
    create_exception_handlers_decorator,
)


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


def test_http_error_map_handler_factory(fake_request: web.Request):

    exc_handler = create__http_error_map_handler(
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


def test_handled_exception_context(fake_request: web.Request):
    def _suppress_handler(exception, request):
        assert request == fake_request
        assert isinstance(
            exception, BasePluginError
        ), "only BasePluginError exceptions should call this handler"
        return None  # noqa: RET501, PLR1711

    def _fun(raises):
        with _handled_exception_context(
            BasePluginError, _suppress_handler, request=fake_request
        ):
            raise raises

    # checks
    _fun(raises=OneError)
    _fun(raises=OtherError)

    with pytest.raises(ArithmeticError):
        _fun(raises=ArithmeticError)


async def test_exception_handlers_decorator():
    def _suppress_handler(exception, request):
        assert isinstance(
            exception, BasePluginError
        ), "only BasePluginError exceptions should call this handler"
        return None  # noqa: RET501, PLR1711

    _handle_exceptons = create_exception_handlers_decorator(
        _suppress_handler, BasePluginError
    )

    @_handle_exceptons
    async def _rest_handler(request: web.Request):
        if request.query.get("raise") == "OneError":
            raise OneError
        if request.query.get("raise") == "ArithmeticError":
            raise ArithmeticError

        return web.Response(text="all good")

    # emulates call
    resp = await _rest_handler(make_mocked_request("GET", "/foo"))
    assert resp.status == status.HTTP_200_OK

    # OMG! not good!?
    resp = await _rest_handler(make_mocked_request("GET", "/foo?raise=OneError"))
    assert resp is None

    # typically capture by last
    with pytest.raises(ArithmeticError):
        resp = await _rest_handler(
            make_mocked_request("GET", "/foo?raise=ArithmeticError")
        )
