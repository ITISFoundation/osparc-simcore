# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import textwrap
from collections.abc import AsyncIterator, Iterator
from typing import Final

import httpx
import pytest
import respx
from fastapi import status
from httpx import AsyncClient
from servicelib.fastapi.httpx_utils import (
    retry_on_dropped_connection,
    to_curl_command,
    to_httpx_command,
)
from servicelib.utils_secrets import _PLACEHOLDER


@pytest.fixture
def base_url() -> str:
    return "https://test_base_http_api"


@pytest.fixture
def mock_server_api(base_url: str) -> Iterator[respx.MockRouter]:
    with respx.mock(
        base_url=base_url,
        assert_all_called=False,
        assert_all_mocked=True,  # IMPORTANT: KEEP always True!
    ) as mock:
        mock.get("/").respond(status.HTTP_200_OK)

        mock.post(path__startswith="/foo").respond(status.HTTP_200_OK)
        mock.get(path__startswith="/foo").respond(status.HTTP_200_OK)
        mock.delete(path__startswith="/foo").respond(status.HTTP_200_OK)

        yield mock


@pytest.fixture
async def client(mock_server_api: respx.MockRouter, base_url: str) -> AsyncIterator[AsyncClient]:
    async with httpx.AsyncClient(base_url=base_url) as client:
        yield client


async def test_to_curl_command(client: AsyncClient):
    # with POST
    response = await client.post(
        "/foo",
        params={"x": "3"},
        json={"y": 12},
        headers={"x-secret": "this should not display"},
    )
    assert response.status_code == 200

    cmd_short = to_curl_command(response.request)

    assert (
        cmd_short
        == f'curl -X POST -H "host: test_base_http_api" -H "accept: */*" -H "accept-encoding: gzip, deflate" -H "connection: keep-alive" -H "user-agent: python-httpx/{httpx.__version__}" -H "x-secret: {_PLACEHOLDER}" -H "content-length: 8" -H "content-type: application/json" -d \'{{"y":12}}\' https://test_base_http_api/foo?x=3'  # noqa: E501
    )

    cmd_long = to_curl_command(response.request, use_short_options=False)
    assert cmd_long == cmd_short.replace(
        "-X",
        "--request",
    ).replace(
        "-H",
        "--header",
    ).replace(
        "-d",
        "--data",
    )

    # with GET
    response = await client.get("/foo", params={"x": "3"})
    cmd_multiline = to_curl_command(response.request, multiline=True)

    assert (
        cmd_multiline
        == textwrap.dedent(
            f"""\
        curl \\
        -X GET \\
        -H "host: test_base_http_api" \\
        -H "accept: */*" \\
        -H "accept-encoding: gzip, deflate" \\
        -H "connection: keep-alive" \\
        -H "user-agent: python-httpx/{httpx.__version__}" \\
        https://test_base_http_api/foo?x=3
        """
        ).strip()
    )

    # with DELETE
    response = await client.delete("/foo", params={"x": "3"})
    cmd = to_curl_command(response.request)

    assert "DELETE" in cmd
    assert " -d " not in cmd


async def test_to_httpx_command(client: AsyncClient):
    response = await client.post(
        "/foo",
        params={"x": "3"},
        json={"y": 12},
        headers={"x-secret": "this should not display"},
    )

    cmd_short = to_httpx_command(response.request, multiline=False)

    print(cmd_short)
    assert (
        cmd_short
        == f'httpx -m POST -c \'{{"y":12}}\' -h "host" "test_base_http_api" -h "accept" "*/*" -h "accept-encoding" "gzip, deflate" -h "connection" "keep-alive" -h "user-agent" "python-httpx/{httpx.__version__}" -h "x-secret" "{_PLACEHOLDER}" -h "content-length" "8" -h "content-type" "application/json" https://test_base_http_api/foo?x=3'  # noqa: E501
    )


_DROPPED_CONNECTION_ERRORS: Final[list[Exception]] = [
    httpx.RemoteProtocolError("Server disconnected without sending a response."),
    httpx.ReadError("Connection reset by peer"),
]


@pytest.mark.parametrize("error", _DROPPED_CONNECTION_ERRORS, ids=lambda e: type(e).__name__)
async def test_retry_on_dropped_connection_retries_once(error: Exception):
    calls = 0

    @retry_on_dropped_connection
    async def _get() -> str:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise error
        return "ok"

    assert await _get() == "ok"
    assert calls == 2


@pytest.mark.parametrize(
    "error, expected_calls",
    [
        (httpx.RemoteProtocolError("Server disconnected without sending a response."), 2),
        (httpx.ReadTimeout("timed out"), 1),
    ],
    ids=["dropped-connection-retried-once", "timeout-not-retried"],
)
async def test_retry_on_dropped_connection_gives_up(error: Exception, expected_calls: int):
    calls = 0

    @retry_on_dropped_connection
    async def _get() -> str:
        nonlocal calls
        calls += 1
        raise error

    with pytest.raises(type(error)):
        await _get()
    assert calls == expected_calls
