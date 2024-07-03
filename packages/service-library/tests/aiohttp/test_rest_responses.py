# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import itertools

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
from servicelib.aiohttp import status
from servicelib.aiohttp.rest_responses import (
    _STATUS_CODE_TO_HTTP_ERRORS,
    create_http_error,
    exception_to_response,
    get_http_error,
)
from servicelib.mimetype_constants import MIMETYPE_APPLICATION_JSON

#

# SEE https://httpstatuses.com/
# - below 1xx  -> invalid
BELOW_1XX = (-5, 0, 5, 99)
# - below 4xx  -> not errors
NONE_ERRORS = (HTTPOk.status_code, HTTPNotModified.status_code)
# - above 599 -> invalid
ABOVE_599 = (600, 10000.1)


@pytest.mark.parametrize(
    "http_exc", (HTTPBadRequest, HTTPGone, HTTPInternalServerError)
)
def test_get_http_exception_class_from_code(http_exc: HTTPException):
    assert get_http_error(http_exc.status_code) == http_exc


@pytest.mark.parametrize(
    "status_code", itertools.chain(BELOW_1XX, NONE_ERRORS, ABOVE_599)
)
def test_get_none_for_invalid_or_not_errors_code(status_code):
    assert get_http_error(status_code) is None


@pytest.mark.parametrize(
    "status_code, http_error_cls", _STATUS_CODE_TO_HTTP_ERRORS.items()
)
def test_collected_http_errors_map(status_code: int, http_error_cls: type[HTTPError]):
    assert 399 < status_code < 600, "expected 4XX, 5XX"
    assert http_error_cls.status_code == status_code

    assert http_error_cls != HTTPError
    assert issubclass(http_error_cls, HTTPError)


@pytest.mark.parametrize("skip_details", [True, False])
def tests_exception_to_response(skip_details: bool):
    exception = create_http_error(
        errors=[RuntimeError("foo")],
        reason="Something whent wrong",
        http_error_cls=web.HTTPInternalServerError,
        skip_internal_error_details=skip_details,
    )

    # For now until deprecated SEE https://github.com/aio-libs/aiohttp/issues/2415
    assert isinstance(exception, Exception)
    assert isinstance(exception, web.Response)
    assert hasattr(exception, "__http_exception__")

    # until they have exception.make_response(), we user
    response = exception_to_response(exception)
    assert isinstance(response, web.Response)
    assert not isinstance(response, Exception)
    assert not hasattr(response, "__http_exception__")

    assert response.content_type == MIMETYPE_APPLICATION_JSON
    assert response.status == status.HTTP_500_INTERNAL_SERVER_ERROR
    assert response.text
    assert response.body
