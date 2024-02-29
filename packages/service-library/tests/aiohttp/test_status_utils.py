from servicelib.aiohttp import status
from servicelib.status_utils import (
    get_display_phrase,
    is_client_error,
    is_error,
    is_informational,
    is_redirect,
    is_server_error,
    is_success,
)


def test_display():
    assert get_display_phrase(status.HTTP_200_OK) == "200:OK"

    assert get_display_phrase(11) == ""


def test_status_codes_checks():

    assert is_informational(status.HTTP_102_PROCESSING)
    assert is_success(status.HTTP_202_ACCEPTED)
    assert is_redirect(status.HTTP_301_MOVED_PERMANENTLY)

    assert is_client_error(status.HTTP_401_UNAUTHORIZED)
    assert is_server_error(status.HTTP_503_SERVICE_UNAVAILABLE)

    assert is_error(status.HTTP_401_UNAUTHORIZED)
    assert is_error(status.HTTP_503_SERVICE_UNAVAILABLE)
