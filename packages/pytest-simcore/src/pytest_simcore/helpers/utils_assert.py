""" Extends assertions for testing

"""
from aiohttp import web

from pprint import pformat
from servicelib.rest_responses import unwrap_envelope


async def assert_status(
    response: web.Response, expected_cls: web.HTTPException, expected_msg: str = None
):
    """
    Asserts for enveloped responses
    """
    data, error = unwrap_envelope(await response.json())
    assert (
        response.status == expected_cls.status_code
    ), f"received: ({data},{error}), \nexpected ({expected_cls.status_code}, {expected_msg})"

    if issubclass(expected_cls, web.HTTPError):
        do_assert_error(data, error, expected_cls, expected_msg)

    elif issubclass(expected_cls, web.HTTPNoContent):
        assert not data, pformat(data)
        assert not error, pformat(error)
    else:
        # with a 200, data may still be empty see
        # https://medium.com/@santhoshkumarkrishna/http-get-rest-api-no-content-404-vs-204-vs-200-6dd869e3af1d
        # assert data is not None, pformat(data)
        assert not error, pformat(error)

        if expected_msg:
            assert expected_msg in data["message"]

    return data, error


async def assert_error(
    response: web.Response, expected_cls: web.HTTPException, expected_msg: str = None
):
    data, error = unwrap_envelope(await response.json())
    return do_assert_error(data, error, expected_cls, expected_msg)


def do_assert_error(
    data, error, expected_cls: web.HTTPException, expected_msg: str = None
):
    assert not data, pformat(data)
    assert error, pformat(error)

    assert len(error["errors"]) == 1

    err = error["errors"][0]
    if expected_msg:
        assert expected_msg in err["message"]

    if expected_cls != web.HTTPInternalServerError:
        # otherwise, code is exactly the name of the Exception class
        assert expected_cls.__name__ == err["code"]

    return data, error
