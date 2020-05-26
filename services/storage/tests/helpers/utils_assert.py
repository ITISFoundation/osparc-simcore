from pprint import pformat

from aiohttp import web

from servicelib.rest_responses import unwrap_envelope


async def assert_status(
    response: web.Response, expected_cls: web.HTTPException, expected_msg: str = None
):
    data, error = unwrap_envelope(await response.json())
    assert (
        response.status == expected_cls.status_code
    ), f"got {response.status}, expected {expected_cls.status_code}:\n data:{data},\n error:{error}"

    if issubclass(expected_cls, web.HTTPError):
        do_assert_error(data, error, expected_cls, expected_msg)

    elif issubclass(expected_cls, web.HTTPNoContent):
        assert not data, pformat(data)
        assert not error, pformat(error)
    else:
        assert data is not None, pformat(data)
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

    # TODO: improve error messages
    assert len(error["errors"]) == 1

    err = error["errors"][0]
    if expected_msg:
        assert expected_msg in err["message"]
    assert expected_cls.__name__ == err["code"]

    return data, error
