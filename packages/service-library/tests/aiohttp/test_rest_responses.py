# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import itertools
from typing import Type

import pytest
from aiohttp.web_exceptions import (
    HTTPBadRequest,
    HTTPError,
    HTTPException,
    HTTPGone,
    HTTPInternalServerError,
    HTTPNotModified,
    HTTPOk,
)
from servicelib.aiohttp.rest_responses import (
    _STATUS_CODE_TO_HTTP_ERRORS,
    get_http_error,
)

## HELPERS

# SEE https://httpstatuses.com/
# - below 1xx  -> invalid
BELOW_1XX = (-5, 0, 5, 99)
# - below 4xx  -> not errors
NONE_ERRORS = (HTTPOk.status_code, HTTPNotModified.status_code)
# - above 599 -> invalid
ABOVE_599 = (600, 10000.1)


## FIXTURES


## TESTS


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
def test_collected_http_errors_map(status_code: int, http_error_cls: Type[HTTPError]):
    assert 399 < status_code < 600, "expected 4XX, 5XX"
    assert http_error_cls.status_code == status_code

    assert http_error_cls != HTTPError
    assert issubclass(http_error_cls, HTTPError)
