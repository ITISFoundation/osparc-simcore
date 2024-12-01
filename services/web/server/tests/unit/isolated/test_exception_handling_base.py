# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=too-many-statements
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import pytest
from aiohttp import web
from aiohttp.test_utils import make_mocked_request
from simcore_service_webserver.errors import WebServerBaseError
from simcore_service_webserver.exception_handling._base import (
    AiohttpExceptionHandler,
    ExceptionHandlingContextManager,
    _sort_exceptions_by_specificity,
    exception_handling_decorator,
)

# Some custom errors in my service


class BaseError(WebServerBaseError):
    ...


class OneError(BaseError):
    ...


class OtherError(BaseError):
    ...


def test_sort_concrete_first():
    assert _sort_exceptions_by_specificity([Exception, BaseError]) == [
        BaseError,
        Exception,
    ]

    assert _sort_exceptions_by_specificity(
        [Exception, BaseError], concrete_first=False
    ) == [
        Exception,
        BaseError,
    ]


def test_sort_exceptions_by_specificity():

    got_exceptions_cls = _sort_exceptions_by_specificity(
        [
            Exception,
            OtherError,
            OneError,
            BaseError,
            ValueError,
            ArithmeticError,
            ZeroDivisionError,
        ]
    )

    for from_, exc in enumerate(got_exceptions_cls, start=1):
        for exc_after in got_exceptions_cls[from_:]:
            assert not issubclass(exc_after, exc), f"{got_exceptions_cls=}"


async def test__handled_exception_context_manager():

    expected_request = make_mocked_request("GET", "/foo")
    expected_response = web.json_response({"error": {"msg": "Foo"}})

    # define exception-handler function
    async def _base_exc_handler(request, exception):
        assert request == expected_request
        assert isinstance(exception, BaseError)
        assert not isinstance(exception, OtherError)
        return expected_response

    async def _concrete_exc_handler(request, exception):
        assert request == expected_request
        assert isinstance(exception, OtherError)
        return expected_response

    exception_handlers_map: dict[type[BaseException], AiohttpExceptionHandler] = {
        BaseError: _base_exc_handler,
        OtherError: _concrete_exc_handler,
    }

    # handles any BaseError returning a response
    cm = ExceptionHandlingContextManager(
        exception_handlers_map, request=expected_request
    )
    async with cm:
        raise OneError
    assert cm.get_response_or_none() == expected_response

    async with cm:
        raise OtherError
    assert cm.get_response_or_none() == expected_response

    # reraises
    with pytest.raises(ArithmeticError):
        async with cm:
            raise ArithmeticError


@pytest.mark.parametrize("exception_cls", [OneError, OtherError])
async def test_async_try_except_decorator(exception_cls: type[Exception]):
    expected_request = make_mocked_request("GET", "/foo")
    expected_exception = exception_cls()
    expected_response = web.Response(reason=f"suppressed {exception_cls}")

    # creates exception handler
    async def _suppress_all(request: web.Request, exception):
        assert exception == expected_exception
        assert request == expected_request
        return expected_response

    @exception_handling_decorator({BaseError: _suppress_all})
    async def _rest_handler(request: web.Request) -> web.Response:
        raise expected_exception

    # emulates request/response workflow
    resp = await _rest_handler(expected_request)
    assert resp == expected_response
