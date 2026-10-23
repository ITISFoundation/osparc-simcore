# pylint: disable=redefined-outer-name

from collections.abc import Callable
from typing import Any, Final
from uuid import uuid4

import httpx
import pytest
from fastapi import status
from simcore_service_api_server.services_http.storage import StorageApi


def _storage_api(handler: Callable[[httpx.Request], httpx.Response]) -> StorageApi:
    client = httpx.AsyncClient(base_url="http://storage:8080/v0", transport=httpx.MockTransport(handler))
    return StorageApi(client=client, service_name="Storage")


def _empty_search_response() -> httpx.Response:
    return httpx.Response(status.HTTP_200_OK, json={"data": []})


_SEARCHES: Final[list[tuple[str, dict[str, Any]]]] = [
    ("list_files", {"user_id": 1}),
    ("search_owned_files", {"user_id": 1, "file_id": uuid4()}),
]


@pytest.mark.parametrize(
    "dropped_connection_error",
    [
        httpx.RemoteProtocolError("Server disconnected without sending a response."),
        httpx.ReadError("Connection reset by peer"),
    ],
    ids=lambda e: type(e).__name__,
)
@pytest.mark.parametrize("method_name, kwargs", _SEARCHES)
async def test_searches_retry_once_when_connection_is_dropped(
    method_name: str, kwargs: dict[str, Any], dropped_connection_error: Exception
):
    calls: list[httpx.Request] = []

    def _handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        if len(calls) == 1:
            raise dropped_connection_error
        return _empty_search_response()

    api = _storage_api(_handler)

    assert await getattr(api, method_name)(**kwargs) == []
    assert len(calls) == 2


@pytest.mark.parametrize(
    "error, expected_calls",
    [
        (httpx.RemoteProtocolError("Server disconnected without sending a response."), 2),
        (httpx.ReadTimeout("timed out"), 1),
    ],
    ids=["dropped-connection-retried-once", "timeout-not-retried"],
)
async def test_search_gives_up_after_failed_attempts(error: Exception, expected_calls: int):
    calls: list[httpx.Request] = []

    def _handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        raise error

    api = _storage_api(_handler)

    with pytest.raises(type(error)):
        await api.search_owned_files(user_id=1, file_id=None)
    assert len(calls) == expected_calls
