# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

from asyncio import BaseEventLoop

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient
from simcore_sdk.node_ports_common.file_io_utils import (
    ExtendedClientResponseError,
    _raise_for_status,
)

TEST_ERROR = "OPSIE there was an error here"


@pytest.fixture
def test_client(loop: BaseEventLoop, aiohttp_client) -> TestClient:
    async def raise_error(request):
        return web.Response(body=TEST_ERROR, status=web.HTTPBadRequest.status_code)

    app = web.Application()
    app.router.add_get("/", raise_error)
    return loop.run_until_complete(aiohttp_client(app))


async def test_raise_for_status(test_client: TestClient):
    resp = await test_client.get("/")
    with pytest.raises(ExtendedClientResponseError) as exe_info:
        await _raise_for_status(resp)
    assert TEST_ERROR in f"{exe_info.value}"
