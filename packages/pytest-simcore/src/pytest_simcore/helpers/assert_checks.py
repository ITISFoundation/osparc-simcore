""" Extends assertions for testing

"""
from http import HTTPStatus
from pprint import pformat

from aiohttp import ClientResponse
from servicelib.aiohttp import status
from servicelib.aiohttp.rest_responses import unwrap_envelope
from servicelib.status_codes_utils import get_code_display_name, is_error


async def assert_status(
    response: ClientResponse,
    expected_status_code: int,
    expected_msg: str | None = None,
    expected_error_code: str | None = None,
    *,
    include_meta: bool | None = False,
    include_links: bool | None = False,
) -> tuple[dict, ...]:
    """
    Asserts for enveloped responses
    """
    # raises ValueError if cannot be converted
    expected_status_code = HTTPStatus(expected_status_code)

    # reponse
    json_response = await response.json()
    data, error = unwrap_envelope(json_response)

    assert response.status == expected_status_code, (
        f"received {response.status}: ({data},{error})"
        f", expected {get_code_display_name(expected_status_code)} : {expected_msg or ''}"
    )

    if is_error(expected_status_code):
        _do_assert_error(
            data, error, expected_status_code, expected_msg, expected_error_code
        )

    elif expected_status_code == status.HTTP_204_NO_CONTENT:
        assert not data, pformat(data)
        assert not error, pformat(error)
    else:
        # with a 200, data may still be empty so we cannot 'assert data is not None'
        # SEE https://medium.com/@santhoshkumarkrishna/http-get-rest-api-no-content-404-vs-204-vs-200-6dd869e3af1d
        assert not error, pformat(error)

        if expected_msg:
            assert expected_msg in data["message"]

    return_value = (
        data,
        error,
    )
    if include_meta:
        return_value += (json_response.get("_meta"),)
    if include_links:
        return_value += (json_response.get("_links"),)
    return return_value


async def assert_error(
    response: ClientResponse,
    expected_status_code: int,
    expected_msg: str | None = None,
):
    data, error = unwrap_envelope(await response.json())
    return _do_assert_error(data, error, expected_status_code, expected_msg)


def _do_assert_error(
    data,
    error,
    expected_status_code: int,
    expected_msg: str | None = None,
    expected_error_code: str | None = None,
):
    assert not data, pformat(data)
    assert error, pformat(error)

    assert is_error(expected_status_code)

    # New versions of the error models might not have this attribute
    details = error.get("errors", [])

    if expected_msg:
        assert details
        messages = [e["message"] for e in details]
        assert expected_msg in messages

    if expected_error_code:
        assert details
        codes = [e["code"] for e in details]
        assert expected_error_code in codes

    return data, error
