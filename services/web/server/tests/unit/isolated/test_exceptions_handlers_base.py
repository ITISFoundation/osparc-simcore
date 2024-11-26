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
from simcore_service_webserver.exceptions_handlers_base import (
    _handled_exception_context_manager,
    create_decorator_from_exception_handler,
)

# Some custom errors in my service


class BaseError(WebServerBaseError):
    ...


class OneError(BaseError):
    ...


class OtherError(BaseError):
    ...


async def test__handled_exception_context_manager():

    expected_request = make_mocked_request("GET", "/foo")
    expected_response = web.json_response({"error": {"msg": "Foo"}})

    # define exception-handler function
    async def _custom_handler(request, exception):
        assert request == expected_request
        assert isinstance(
            exception, BaseError
        ), "only BasePluginError exceptions should call this handler"
        return expected_response

    # exception-handler -> context manager

    # handles any BaseError returning a response
    async with _handled_exception_context_manager(
        BaseError, _custom_handler, request=expected_request
    ) as ctx1:
        raise OneError
    assert ctx1.response == expected_response

    async with _handled_exception_context_manager(
        BaseError, _custom_handler, request=expected_request
    ) as ctx2:
        raise OtherError
    assert ctx2.response == expected_response

    # otherwise thru
    with pytest.raises(ArithmeticError):
        async with _handled_exception_context_manager(
            BaseError, _custom_handler, request=expected_request
        ):
            raise ArithmeticError


@pytest.mark.parametrize("exception_cls", [OneError, OtherError])
async def test_create_decorator_from_exception_handler(exception_cls: type[Exception]):
    expected_request = make_mocked_request("GET", "/foo")
    expected_exception = exception_cls()
    expected_response = web.Response(reason="suppressed")

    # creates exception handler
    async def _suppress_all(request: web.Request, exception):
        assert exception == expected_exception
        assert request == expected_request
        return expected_response

    # create a decorator
    _exc_handling_decorator = create_decorator_from_exception_handler(
        exception_types=BaseError,  # NOTE: base class
        exception_handler=_suppress_all,
    )

    # using decorators
    @_exc_handling_decorator
    async def _rest_handler(request: web.Request) -> web.Response:
        raise expected_exception

    # emulates request/response workflow
    resp = await _rest_handler(expected_request)
    assert resp == expected_response
