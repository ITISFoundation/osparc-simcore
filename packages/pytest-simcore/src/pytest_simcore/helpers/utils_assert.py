""" Extends assertions for testing

"""
from pprint import pformat

from aiohttp import ClientResponse
from aiohttp.web import HTTPError, HTTPException, HTTPInternalServerError, HTTPNoContent
from servicelib.aiohttp.rest_responses import unwrap_envelope


async def assert_status(
    response: ClientResponse,
    expected_cls: type[HTTPException],
    expected_msg: str | None = None,
    expected_error_code: str | None = None,
    include_meta: bool | None = False,
    include_links: bool | None = False,
) -> tuple[dict, ...]:
    """
    Asserts for enveloped responses
    """
    json_response = await response.json()
    data, error = unwrap_envelope(json_response)
    assert response.status == expected_cls.status_code, (
        f"received {response.status}: ({data},{error})"
        f", expected {expected_cls.status_code} : {expected_msg or ''}"
    )

    if issubclass(expected_cls, HTTPError):
        do_assert_error(data, error, expected_cls, expected_msg, expected_error_code)

    elif issubclass(expected_cls, HTTPNoContent):
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
    expected_cls: type[HTTPException],
    expected_msg: str | None = None,
):
    data, error = unwrap_envelope(await response.json())
    return do_assert_error(data, error, expected_cls, expected_msg)


def do_assert_error(
    data,
    error,
    expected_cls: type[HTTPException],
    expected_msg: str | None = None,
    expected_error_code: str | None = None,
):
    assert not data, pformat(data)
    assert error, pformat(error)

    assert len(error["errors"]) == 1

    err = error["errors"][0]
    if expected_msg:
        assert expected_msg in err["message"]

    if expected_error_code:
        assert expected_error_code == err["code"]
    elif expected_cls != HTTPInternalServerError:
        # otherwise, code is exactly the name of the Exception class
        assert expected_cls.__name__ == err["code"]

    return data, error
