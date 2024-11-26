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
from servicelib.mimetype_constants import MIMETYPE_APPLICATION_JSON
from simcore_service_webserver.errors import WebServerBaseError
from simcore_service_webserver.exceptions_handlers_base import (
    AsyncDynamicTryExceptContext,
)
from simcore_service_webserver.exceptions_handlers_http_error_map import (
    ExceptionToHttpErrorMap,
    HttpErrorInfo,
    create_exception_handler_from_http_error,
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
    one_error_to_404 = create_exception_handler_from_http_error(
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


async def test_factory__create_exception_handler_from_http_error_map(
    fake_request: web.Request,
):
    exc_to_http_error_map: ExceptionToHttpErrorMap = {
        OneError: HttpErrorInfo(status.HTTP_400_BAD_REQUEST, "Error One mapped to 400")
    }

    cm = AsyncDynamicTryExceptContext(
        to_exceptions_handlers_map(exc_to_http_error_map), request=fake_request
    )
    async with cm:
        raise OneError

    response = cm.get_response()
    assert response is not None
    assert response.status == status.HTTP_400_BAD_REQUEST
    assert response.reason == "Error One mapped to 400"

    # By-passes exceptions not listed
    err = RuntimeError()
    with pytest.raises(RuntimeError) as err_info:
        async with cm:
            raise err

    assert cm.get_response() is None
    assert err_info.value == err


# async def test__handled_exception_context_manager(fake_request: web.Request):

#     expected_response = web.json_response({"error": {"msg": "Foo"}})

#     async def _custom_handler(request, exception):
#         assert request == fake_request
#         assert isinstance(
#             exception, BaseError
#         ), "only BasePluginError exceptions should call this handler"
#         return expected_response

#     exc_handling_ctx = _handled_exception_context_manager(
#         BaseError, _custom_handler, request=fake_request
#     )

#     # handles any BaseError returning a response
#     async with exc_handling_ctx as ctx:
#         raise OneError
#     assert ctx.response == expected_response

#     async with exc_handling_ctx as ctx:
#         raise OtherError
#     assert ctx.response == expected_response

#     # otherwise thru
#     with pytest.raises(ArithmeticError):
#         async with exc_handling_ctx:
#             raise ArithmeticError


# async def test_create_decorator_from_exception_handler(
#     caplog: pytest.LogCaptureFixture,
# ):
#     # Create an SINGLE exception handler that acts as umbrella for all these exceptions
#     http_error_map: ExceptionToHttpErrorMap = {
#         OneError: HttpErrorInfo(
#             status.HTTP_503_SERVICE_UNAVAILABLE,
#             "Human readable error transmitted to the front-end",
#         )
#     }

#     exc_handler = create_exception_handler_from_http_error_map(http_error_map)
#     _exc_handling_ctx = create_decorator_from_exception_handler(
#         exception_types=BaseError,  # <--- FIXME" this is redundant because exception has been already passed in exc_handler!
#         exception_handler=exc_handler,
#     )

#     @_exc_handling_ctx
#     async def _rest_handler(request: web.Request) -> web.Response:
#         if request.query.get("raise") == "OneError":
#             raise OneError
#         if request.query.get("raise") == "ArithmeticError":
#             raise ArithmeticError

#         return web.Response(reason="all good")

#     with caplog.at_level(logging.ERROR):

#         # emulates successful call
#         resp = await _rest_handler(make_mocked_request("GET", "/foo"))
#         assert resp.status == status.HTTP_200_OK
#         assert resp.reason == "all good"

#         assert not caplog.records

#         # this will be passed and catched by the outermost error middleware
#         with pytest.raises(ArithmeticError):
#             await _rest_handler(
#                 make_mocked_request("GET", "/foo?raise=ArithmeticError")
#             )

#         assert not caplog.records

#         # this is a 5XX will be converted to response but is logged as error as well
#         with pytest.raises(web.HTTPException) as exc_info:
#             await _rest_handler(make_mocked_request("GET", "/foo?raise=OneError"))

#         resp = exc_info.value
#         assert resp.status == status.HTTP_503_SERVICE_UNAVAILABLE
#         assert "front-end" in resp.reason

#         assert caplog.records, "Expected 5XX troubleshooting logged as error"
#         assert caplog.records[0].levelno == logging.ERROR

#     # typically capture by last
#     with pytest.raises(ArithmeticError):
#         resp = await _rest_handler(
#             make_mocked_request("GET", "/foo?raise=ArithmeticError")
#         )
