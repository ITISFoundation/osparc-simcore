# pylint:disable=redefined-outer-name
# pylint:disable=unused-argument

import datetime
from collections.abc import AsyncIterable
from typing import Any, Final

import pytest
from aiohttp import ClientResponseError, ClientSession
from aiohttp.client_exceptions import ClientConnectionError
from aioresponses import aioresponses
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict
from servicelib.aiohttp import status
from simcore_sdk.node_ports_common import exceptions
from simcore_sdk.node_ports_common.storage_client import handle_client_exception, retry_request

_ROUTE_ALWAYS_200_OK: Final[str] = "http://always-200-ok"

_MOCK_RESPONSE_BODY: Final[dict[str, Any]] = {"data": "mock_body"}


@pytest.fixture
def mock_responses(aioresponses_mocker: aioresponses) -> None:
    aioresponses_mocker.get(_ROUTE_ALWAYS_200_OK, status=200, payload=_MOCK_RESPONSE_BODY)


@pytest.fixture
def mock_postgres(monkeypatch: pytest.MonkeyPatch) -> None:
    setenvs_from_dict(
        monkeypatch,
        {
            "POSTGRES_HOST": "test",
            "POSTGRES_USER": "test",
            "POSTGRES_PASSWORD": "test",
            "POSTGRES_DB": "test",
        },
    )


@pytest.fixture
async def session(mock_postgres: None) -> AsyncIterable[ClientSession]:
    async with ClientSession() as client_session:
        yield client_session


@pytest.mark.parametrize(
    "status_code,expected_error",
    [
        (status.HTTP_400_BAD_REQUEST, exceptions.StorageInvalidCallError),
        (status.HTTP_404_NOT_FOUND, exceptions.S3InvalidPathError),
        (status.HTTP_422_UNPROCESSABLE_CONTENT, exceptions.StorageInvalidCallError),
        (status.HTTP_500_INTERNAL_SERVER_ERROR, exceptions.StorageServerIssueError),
        (status.HTTP_503_SERVICE_UNAVAILABLE, exceptions.StorageServerIssueError),
    ],
)
async def test_handle_client_exception_maps_response_status(
    status_code: int,
    expected_error: type[Exception],
    aioresponses_mocker: aioresponses,
    session: ClientSession,
):
    """every response status must reach node-ports as a NodeportsError"""

    @handle_client_exception
    async def _request():
        async with session.get(_ROUTE_ALWAYS_200_OK) as response:
            response.raise_for_status()

    aioresponses_mocker.get(_ROUTE_ALWAYS_200_OK, status=status_code, payload=_MOCK_RESPONSE_BODY)

    with pytest.raises(expected_error):
        await _request()


async def test_retry_request_ok(mock_responses: None, session: ClientSession):
    async with retry_request(session, "GET", _ROUTE_ALWAYS_200_OK, expected_status=200) as response:
        assert response.status == 200
        assert await response.json() == _MOCK_RESPONSE_BODY


async def test_retry_request_unexpected_code(mock_responses: None, session: ClientSession):
    with pytest.raises(ClientResponseError, match="but was expecting"):
        async with retry_request(session, "GET", _ROUTE_ALWAYS_200_OK, expected_status=999):
            ...


async def test_retry_retries_before_giving_up(session: ClientSession, caplog: pytest.LogCaptureFixture):
    caplog.clear()
    with pytest.raises(ClientConnectionError, match="Cannot connect to host"):
        async with retry_request(
            session,
            "GET",
            "http://this-route-does-not-exist.local",
            expected_status=200,
            give_up_after=datetime.timedelta(seconds=1),
        ):
            ...

    assert "unexpected error:" in caplog.text
