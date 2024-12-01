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
from servicelib.mimetype_constants import MIMETYPE_APPLICATION_JSON
from simcore_service_webserver.errors import WebServerBaseError
from simcore_service_webserver.exception_handling._base import (
    ExceptionHandlingContextManager,
    exception_handling_decorator,
)
from simcore_service_webserver.exception_handling._factory import (
    ExceptionToHttpErrorMap,
    HttpErrorInfo,
    create_exception_handler_from_http_info,
    to_exceptions_handlers_map,
)

# Some custom errors in my service


class BaseError(WebServerBaseError):
    ...


class OneError(BaseError):
    ...


class OtherError(BaseError):
    ...


@pytest.fixture
def fake_request() -> web.Request:
    return make_mocked_request("GET", "/foo")


async def test_factory__create_exception_handler_from_http_error(
    fake_request: web.Request,
):
    one_error_to_404 = create_exception_handler_from_http_info(
        status_code=status.HTTP_404_NOT_FOUND,
        msg_template="one error message for the user: {code} {value}",
    )

    # calling exception handler
    caught = OneError()
    response = await one_error_to_404(fake_request, caught)
    assert response.status == status.HTTP_404_NOT_FOUND
    assert response.text is not None
    assert "one error message" in response.reason
    assert response.content_type == MIMETYPE_APPLICATION_JSON


async def test_handling_different_exceptions_with_context(
    fake_request: web.Request,
    caplog: pytest.LogCaptureFixture,
):
    exc_to_http_error_map: ExceptionToHttpErrorMap = {
        OneError: HttpErrorInfo(status.HTTP_400_BAD_REQUEST, "Error {code} to 400"),
        OtherError: HttpErrorInfo(status.HTTP_500_INTERNAL_SERVER_ERROR, "{code}"),
    }
    cm = ExceptionHandlingContextManager(
        to_exceptions_handlers_map(exc_to_http_error_map), request=fake_request
    )

    with caplog.at_level(logging.ERROR):
        # handles as 4XX
        async with cm:
            raise OneError

        response = cm.get_response_or_none()
        assert response is not None
        assert response.status == status.HTTP_400_BAD_REQUEST
        assert response.reason == exc_to_http_error_map[OneError].msg_template.format(
            code="WebServerBaseError.BaseError.OneError"
        )
        assert not caplog.records

        # unhandled -> reraises
        err = RuntimeError()
        with pytest.raises(RuntimeError) as err_info:
            async with cm:
                raise err

        assert cm.get_response_or_none() is None
        assert err_info.value == err

        # handles as 5XX and logs
        async with cm:
            raise OtherError

        response = cm.get_response_or_none()
        assert response is not None
        assert response.status == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert response.reason == exc_to_http_error_map[OtherError].msg_template.format(
            code="WebServerBaseError.BaseError.OtherError"
        )
        assert caplog.records, "Expected 5XX troubleshooting logged as error"
        assert caplog.records[0].levelno == logging.ERROR


async def test_handling_different_exceptions_with_decorator(
    fake_request: web.Request,
    caplog: pytest.LogCaptureFixture,
):
    exc_to_http_error_map: ExceptionToHttpErrorMap = {
        OneError: HttpErrorInfo(status.HTTP_503_SERVICE_UNAVAILABLE, "{code}"),
    }

    exc_handling_decorator = exception_handling_decorator(
        to_exceptions_handlers_map(exc_to_http_error_map)
    )

    @exc_handling_decorator
    async def _rest_handler(request: web.Request) -> web.Response:
        if request.query.get("raise") == "OneError":
            raise OneError
        if request.query.get("raise") == "ArithmeticError":
            raise ArithmeticError
        return web.json_response(reason="all good")

    with caplog.at_level(logging.ERROR):

        # emulates successful call
        resp = await _rest_handler(make_mocked_request("GET", "/foo"))
        assert resp.status == status.HTTP_200_OK
        assert resp.reason == "all good"

        assert not caplog.records

        # reraised
        with pytest.raises(ArithmeticError):
            await _rest_handler(
                make_mocked_request("GET", "/foo?raise=ArithmeticError")
            )

        assert not caplog.records

        # handles as 5XX and logs
        resp = await _rest_handler(make_mocked_request("GET", "/foo?raise=OneError"))
        assert resp.status == status.HTTP_503_SERVICE_UNAVAILABLE
        assert caplog.records, "Expected 5XX troubleshooting logged as error"
        assert caplog.records[0].levelno == logging.ERROR
