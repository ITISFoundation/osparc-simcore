from http import HTTPStatus

from servicelib.aiohttp import status
from servicelib.status_utils import (
    get_display_phrase,
    get_http_status_codes,
    is_client_error,
    is_error,
    is_informational,
    is_redirect,
    is_server_error,
    is_success,
)


def test_display():
    assert get_display_phrase(status.HTTP_200_OK) == "200:OK"

    assert get_display_phrase(11) == "11"
    assert get_display_phrase(status.HTTP_306_RESERVED) == "306"


def test_status_codes_checks():

    assert is_informational(status.HTTP_102_PROCESSING)
    assert is_success(status.HTTP_202_ACCEPTED)
    assert is_redirect(status.HTTP_301_MOVED_PERMANENTLY)

    assert is_client_error(status.HTTP_401_UNAUTHORIZED)
    assert is_server_error(status.HTTP_503_SERVICE_UNAVAILABLE)

    assert is_error(status.HTTP_401_UNAUTHORIZED)
    assert is_error(status.HTTP_503_SERVICE_UNAVAILABLE)


def test_predicates_with_status():

    # in formational
    assert get_http_status_codes(status, is_informational) == [
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
