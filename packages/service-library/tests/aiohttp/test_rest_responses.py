# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import pytest
from aiohttp.web_exceptions import (
    HTTPBadRequest,
    HTTPException,
    HTTPInternalServerError,
    HTTPMultipleChoices,
    HTTPOk,
)
from servicelib.aiohttp.rest_responses import get_http_exception


@pytest.mark.parametrize(
    "http_exc", (HTTPOk, HTTPMultipleChoices, HTTPBadRequest, HTTPInternalServerError)
)
def test_get_http_exception_class_from_code(http_exc: HTTPException):
    # in range https://httpstatuses.com/
    assert get_http_exception(http_exc.status_code) == http_exc


def test_get_none_for_invalid_code():
    # above 5xx and below 1xx
    assert get_http_exception(-5) is None
    assert get_http_exception(5) is None
    assert get_http_exception(600) is None

    # in range https://httpstatuses.com/
    assert get_http_exception(200)

    # gaps
    assert get_http_exception(105) is None
    assert get_http_exception(250) is None
