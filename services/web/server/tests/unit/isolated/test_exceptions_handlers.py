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

    def _rest_handler(exc_cls):
        with _handled_exception_context(
            BasePluginError, _suppress_handler, request=fake_request
        ):
            raise exc_cls

    # checks
    _rest_handler(OneError)
    _rest_handler(OtherError)

    with pytest.raises(ArithmeticError):
        _rest_handler(ArithmeticError)
