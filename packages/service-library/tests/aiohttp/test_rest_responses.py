# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import pytest
from aiohttp.web_exceptions import (
    HTTPBadRequest,
    HTTPException,
    HTTPGone,
    HTTPInternalServerError,
)
from servicelib.aiohttp.rest_responses import get_http_error


@pytest.mark.parametrize(
    "http_exc", (HTTPBadRequest, HTTPGone, HTTPInternalServerError)
)
def test_get_http_exception_class_from_code(http_exc: HTTPException):
    # in range https://httpstatuses.com/
    assert get_http_error(http_exc.status_code) == http_exc


def test_get_none_for_invalid_or_not_errors_code():
    # SEE https://httpstatuses.com/
    # below 1xx  -> invalid
    assert get_http_error(-5) is None
    assert get_http_error(5) is None
    assert get_http_error(600) is None

    # below 4xx  -> not errors
    assert get_http_error(200) is None
    assert get_http_error(300) is None
    assert get_http_error(399) is None

    # above 599 -> invalid
    assert get_http_error(600) is None
