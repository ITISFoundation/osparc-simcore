from http import HTTPStatus

import pytest
from servicelib.aiohttp import status
from servicelib.aiohttp.web_exceptions_extension import (
    STATUS_CODES_WITHOUT_AIOHTTP_EXCEPTION_CLASS,
    HTTPException,
    get_all_aiohttp_http_exceptions,
)
from servicelib.status_codes_utils import (
    _INVALID_STATUS_CODE_MSG,
    get_code_description,
    get_code_display_name,
    get_http_status_codes,
    is_1xx_informational,
    is_2xx_success,
    is_3xx_redirect,
    is_4xx_client_error,
    is_5xx_server_error,
    is_error,
)


def test_display():
    assert get_code_display_name(status.HTTP_200_OK) == "HTTP_200_OK"
    assert get_code_display_name(status.HTTP_306_RESERVED) == "HTTP_306_RESERVED"
    assert get_code_display_name(11) == _INVALID_STATUS_CODE_MSG


def test_description():
    # SEE https://github.com/python/cpython/blob/main/Lib/http/__init__.py#L54-L171
    assert (
        get_code_description(status.HTTP_200_OK)
        == "Request fulfilled, document follows. See https://developer.mozilla.org/en-US/docs/Web/HTTP/Status/200"
    )


def test_status_codes_checks():

    assert is_1xx_informational(status.HTTP_102_PROCESSING)
    assert is_2xx_success(status.HTTP_202_ACCEPTED)
    assert is_3xx_redirect(status.HTTP_301_MOVED_PERMANENTLY)

    assert is_4xx_client_error(status.HTTP_401_UNAUTHORIZED)
    assert is_5xx_server_error(status.HTTP_503_SERVICE_UNAVAILABLE)

    assert is_error(status.HTTP_401_UNAUTHORIZED)
    assert is_error(status.HTTP_503_SERVICE_UNAVAILABLE)


def test_predicates_with_status():

    # in formational
    assert get_http_status_codes(status, is_1xx_informational) == [
        status.HTTP_100_CONTINUE,
        status.HTTP_101_SWITCHING_PROTOCOLS,
        status.HTTP_102_PROCESSING,
        status.HTTP_103_EARLY_HINTS,
    ]

    # errors
    assert [is_error(c) for c in get_http_status_codes(status, is_error)]

    # all. Curiously 306 is not in HTTPSTatus!
    assert [
        HTTPStatus(c)
        for c in get_http_status_codes(status)
        if c != status.HTTP_306_RESERVED
    ]


AIOHTTP_EXCEPTION_CLASSES_MAP: dict[int, type[HTTPException]] = (
    get_all_aiohttp_http_exceptions(HTTPException)
)


@pytest.mark.parametrize("status_code", get_http_status_codes(status))
def test_how_status_codes_map_to_aiohttp_exception_class(status_code):
    aiohttp_exception_cls = AIOHTTP_EXCEPTION_CLASSES_MAP.get(status_code)
    if status_code in STATUS_CODES_WITHOUT_AIOHTTP_EXCEPTION_CLASS:
        assert aiohttp_exception_cls is None
    else:
        assert aiohttp_exception_cls is not None
