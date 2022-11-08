# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

from asyncio import BaseEventLoop

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient
from pytest import FixtureRequest
from simcore_sdk.node_ports_common.file_io_utils import (
    ExtendedClientResponseError,
    _check_for_aws_http_errors,
    _raise_for_status,
)


def _get_test_client(
    mocked_response: web.Response,
    loop: BaseEventLoop,
    aiohttp_client,
) -> TestClient:
    async def raise_error(_: web.Request) -> web.Response:
        return mocked_response

    app = web.Application()
    app.router.add_get("/", raise_error)
    return loop.run_until_complete(aiohttp_client(app))


TEST_ERROR = "OPSIE there was an error here"


@pytest.fixture
def test_client(loop: BaseEventLoop, aiohttp_client) -> TestClient:
    return _get_test_client(
        mocked_response=web.Response(
            body=TEST_ERROR, status=web.HTTPBadRequest.status_code
        ),
        loop=loop,
        aiohttp_client=aiohttp_client,
    )


async def test_raise_for_status(test_client: TestClient):
    resp = await test_client.get("/")
    with pytest.raises(ExtendedClientResponseError) as exe_info:
        await _raise_for_status(resp)
    assert TEST_ERROR in f"{exe_info.value}"


@pytest.fixture(
    params=[
        web.Response(
            status=web.HTTPBadRequest.status_code,
            body=(
                '<?xml version="1.0" encoding="UTF-8"?><Error><Code>RequestTimeout</Code>'
                "<Message>Your socket connection to the server was not read from or written to within "
                "the timeout period. Idle connections will be closed.</Message>"
                "<RequestId>7EE901348D6C6812</RequestId><HostId>"
                "FfQE7jdbUt39E6mcQq/"
                "ZeNR52ghjv60fccNT4gCE4IranXjsGLG+L6FUyiIxx1tAuXL9xtz2NAY7ZlbzMTm94fhY3TBiCBmf"
                "</HostId></Error>"
            ),
        ),
        web.Response(status=web.HTTPInternalServerError.status_code),
        web.Response(status=web.HTTPServiceUnavailable.status_code),
    ]
)
def test_client_2(
    request: FixtureRequest, loop: BaseEventLoop, aiohttp_client
) -> TestClient:
    return _get_test_client(
        mocked_response=request.param, loop=loop, aiohttp_client=aiohttp_client
    )


async def test_retry_on_aws_errors(test_client_2: TestClient):
    resp = await test_client_2.get("/")
    try:
        await _raise_for_status(resp)
    except ExtendedClientResponseError as exception:
        assert _check_for_aws_http_errors(exception) is True
