from aiohttp import web

from servicelib.response_utils import unwrap_envelope


async def assert_status(response: web.Response, expected_cls:web.HTTPException, expected_msg: str=None):
    data, error = unwrap_envelope(await response.json())
    assert response.status == expected_cls.status_code, (data, error)

    if issubclass(expected_cls, web.HTTPError):
        do_assert_error(data, error, expected_cls, expected_msg)
    else:
        assert data
        assert not error

        if expected_msg:
            assert expected_msg in data["message"]

    return data, error

async def assert_error(response: web.Response, expected_cls:web.HTTPException, expected_msg: str=None):
    data, error = unwrap_envelope(await response.json())
    return do_assert_error(data, error, expected_cls, expected_msg)


def do_assert_error(data, error, expected_cls:web.HTTPException, expected_msg: str=None):
    assert not data
    assert error

    # TODO: improve error messages
    assert len(error['errors']) == 1

    err = error['errors'][0]
    if expected_msg:
        assert expected_msg in err['message']
    assert expected_cls.__name__  == err['code']

    return data, error
