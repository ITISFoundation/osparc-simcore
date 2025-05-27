# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import itertools
import json

import pytest
from aiohttp import web
from aiohttp.web_exceptions import (
    HTTPBadRequest,
    HTTPError,
    HTTPException,
    HTTPGone,
    HTTPInternalServerError,
    HTTPNotModified,
    HTTPOk,
)
from common_library.error_codes import ErrorCodeStr, create_error_code
from servicelib.aiohttp import status
from servicelib.aiohttp.rest_responses import create_http_error, exception_to_response
from servicelib.aiohttp.web_exceptions_extension import (
    _STATUS_CODE_TO_HTTP_ERRORS,
    get_http_error_class_or_none,
)
from servicelib.mimetype_constants import MIMETYPE_APPLICATION_JSON

# SEE https://httpstatuses.com/
# - below 1xx  -> invalid
BELOW_1XX = (-5, 0, 5, 99)
# - below 4xx  -> not errors
NONE_ERRORS = (HTTPOk.status_code, HTTPNotModified.status_code)
# - above 599 -> invalid
ABOVE_599 = (600, 10000.1)


@pytest.mark.parametrize(
    "http_exc", [HTTPBadRequest, HTTPGone, HTTPInternalServerError]
)
def test_get_http_exception_class_from_code(http_exc: HTTPException):
    assert get_http_error_class_or_none(http_exc.status_code) == http_exc


@pytest.mark.parametrize(
    "status_code", itertools.chain(BELOW_1XX, NONE_ERRORS, ABOVE_599)
)
def test_get_none_for_invalid_or_not_errors_code(status_code):
    assert get_http_error_class_or_none(status_code) is None


@pytest.mark.parametrize(
    "status_code, http_error_cls", _STATUS_CODE_TO_HTTP_ERRORS.items()
)
def test_collected_http_errors_map(status_code: int, http_error_cls: type[HTTPError]):
    assert 399 < status_code < 600, "expected 4XX, 5XX"
    assert http_error_cls.status_code == status_code

    assert http_error_cls != HTTPError
    assert issubclass(http_error_cls, HTTPError)


@pytest.mark.parametrize("skip_details", [True, False])
@pytest.mark.parametrize("error_code", [None, create_error_code(Exception("fake"))])
def tests_exception_to_response(skip_details: bool, error_code: ErrorCodeStr | None):

    expected_reason = "Something whent wrong !"
    expected_exceptions: list[Exception] = [RuntimeError("foo")]

    http_error = create_http_error(
        errors=expected_exceptions,
        reason=expected_reason,
        http_error_cls=web.HTTPInternalServerError,
        skip_internal_error_details=skip_details,
        error_code=error_code,
    )

    # For now until deprecated SEE https://github.com/aio-libs/aiohttp/issues/2415
    assert isinstance(http_error, Exception)
    assert isinstance(http_error, web.Response)
    assert hasattr(http_error, "__http_exception__")

    # until they have exception.make_response(), we user
    response = exception_to_response(http_error)
    assert isinstance(response, web.Response)
    assert not isinstance(response, Exception)
    assert not hasattr(response, "__http_exception__")

    # checks response components
    assert response.content_type == MIMETYPE_APPLICATION_JSON
    assert response.status == status.HTTP_500_INTERNAL_SERVER_ERROR
    assert response.text
    assert response.body

    # checks response model
    response_json = json.loads(response.text)
    assert response_json["data"] is None
    assert response_json["error"]["message"] == expected_reason
    assert response_json["error"]["supportId"] == error_code
    assert response_json["error"]["status"] == response.status


@pytest.mark.parametrize(
    "input_message, expected_output",
    [
        (None, None),  # None input returns None
        ("", None),  # Empty string returns None
        ("Simple message", "Simple message"),  # Simple message stays the same
        (
            "Message\nwith\nnewlines",
            "Message with newlines",
        ),  # Newlines are replaced with spaces
        ("A" * 2000, "A" * 1500),  # Long message gets truncated to max_length (1500)
        (
            "Line1\nLine2\nLine3" + "X" * 1500,
            "Line1 Line2 Line3" + "X" * 1483,
        ),  # Combined case: newlines and truncation
    ],
    ids=[
        "none_input",
        "empty_string",
        "simple_message",
        "newlines_replaced",
        "long_message_truncated",
        "newlines_and_truncation",
    ],
)
def test_safe_status_message(input_message: str | None, expected_output: str | None):
    from servicelib.aiohttp.rest_responses import safe_status_message

    result = safe_status_message(input_message)
    assert result == expected_output

    # Test with custom max_length
    custom_max = 10
    result_custom = safe_status_message(input_message, max_length=custom_max)

    # Check length constraint is respected
    if result_custom is not None:
        assert len(result_custom) <= custom_max

    # Verify it can be used in a web response without raising exceptions
    try:
        # This would fail with long or multiline reasons
        if result is not None:
            web.Response(reason=result)

        # Test with custom length result too
        if result_custom is not None:
            web.Response(reason=result_custom)
    except ValueError:
        pytest.fail("safe_status_message result caused an exception in web.Response")
