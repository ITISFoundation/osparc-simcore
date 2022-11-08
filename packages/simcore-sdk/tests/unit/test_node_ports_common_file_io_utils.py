# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

from dataclasses import dataclass
from typing import AsyncIterable, Iterable

import pytest
from aiohttp import ClientResponse, ClientSession
from aioresponses import aioresponses
from simcore_sdk.node_ports_common.file_io_utils import (
    ExtendedClientResponseError,
    _check_for_aws_http_errors,
    _raise_for_status,
)

A_TEST_ROUTE = "http://127.0.0.1:1249/test-route"


@pytest.fixture
def mock_service() -> Iterable[aioresponses]:
    with aioresponses() as mock:
        yield mock


@pytest.fixture
async def client_session() -> AsyncIterable[ClientSession]:
    async with ClientSession() as session:
        yield session


async def test_raise_for_status(
    mock_service: aioresponses, client_session: ClientSession
):
    mock_service.get(A_TEST_ROUTE, body="OPSIE there was an error here", status=400)

    async with client_session.get(A_TEST_ROUTE) as resp:
        assert isinstance(resp, ClientResponse)

        with pytest.raises(ExtendedClientResponseError) as exe_info:
            await _raise_for_status(resp)
        assert "OPSIE there was an error here" in f"{exe_info.value}"


@dataclass
class _TestParams:
    will_retry: bool
    status_code: int
    body: str = ""


@pytest.mark.parametrize(
    "test_params",
    [
        _TestParams(
            will_retry=True,
            status_code=400,
            body='<?xml version="1.0" encoding="UTF-8"?><Error><Code>RequestTimeout</Code>'
            "<Message>Your socket connection to the server was not read from or written to within "
            "the timeout period. Idle connections will be closed.</Message>"
            "<RequestId>7EE901348D6C6812</RequestId><HostId>"
            "FfQE7jdbUt39E6mcQq/"
            "ZeNR52ghjv60fccNT4gCE4IranXjsGLG+L6FUyiIxx1tAuXL9xtz2NAY7ZlbzMTm94fhY3TBiCBmf"
            "</HostId></Error>",
        ),
        _TestParams(will_retry=True, status_code=500),
        _TestParams(will_retry=True, status_code=503),
        _TestParams(will_retry=False, status_code=400),
        _TestParams(will_retry=False, status_code=200),
        _TestParams(will_retry=False, status_code=399),
    ],
)
async def test_check_for_aws_http_errors(
    mock_service: aioresponses, client_session: ClientSession, test_params: _TestParams
):
    mock_service.get(
        A_TEST_ROUTE, body=test_params.body, status=test_params.status_code
    )

    async with client_session.get(A_TEST_ROUTE) as resp:
        try:
            await _raise_for_status(resp)
        except ExtendedClientResponseError as exception:
            assert _check_for_aws_http_errors(exception) is test_params.will_retry
