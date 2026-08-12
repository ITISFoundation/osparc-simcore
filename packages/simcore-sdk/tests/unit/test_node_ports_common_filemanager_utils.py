# pylint:disable=redefined-outer-name
# pylint:disable=unused-argument

from collections.abc import AsyncIterable, Iterable
from typing import Any, Final

import pytest
from aiohttp import ClientResponseError, ClientSession
from aioresponses import aioresponses
from pydantic import AnyUrl, TypeAdapter
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict
from servicelib.aiohttp import status
from simcore_sdk.node_ports_common import storage_endpoint
from simcore_sdk.node_ports_common._filemanager_utils import complete_upload

_COMPLETION_LINK: Final[str] = "http://storage:8080/v0/locations/0/files/a-file:complete"
_STATE_LINK: Final[str] = "http://storage:8080/v0/locations/0/files/a-file:complete/futures/a-future"
_E_TAG: Final[str] = "an-e-tag"

_COMPLETION_PAYLOAD: Final[dict[str, Any]] = {"data": {"links": {"state": _STATE_LINK}}}
_STATE_OK_PAYLOAD: Final[dict[str, Any]] = {
    "data": {
        "state": "ok",
        "e_tag": _E_TAG,
        "last_modified": "2026-08-11T06:36:52.672352Z",
    }
}


def _clear_caches() -> None:
    storage_endpoint.is_storage_secure.cache_clear()
    storage_endpoint.get_basic_auth.cache_clear()


@pytest.fixture
def mock_node_ports_env(monkeypatch: pytest.MonkeyPatch) -> Iterable[None]:
    setenvs_from_dict(
        monkeypatch,
        {
            "POSTGRES_HOST": "test",
            "POSTGRES_USER": "test",
            "POSTGRES_PASSWORD": "test",
            "POSTGRES_DB": "test",
            "NODE_PORTS_MULTIPART_UPLOAD_COMPLETION_TIMEOUT_S": "1",
        },
    )
    # NOTE: these read the environment once and cache it for the whole process
    _clear_caches()
    yield
    _clear_caches()


@pytest.fixture
async def session(mock_node_ports_env: None) -> AsyncIterable[ClientSession]:
    async with ClientSession() as client_session:
        yield client_session


@pytest.fixture
def completion_link() -> AnyUrl:
    return TypeAdapter(AnyUrl).validate_python(_COMPLETION_LINK)


@pytest.mark.parametrize(
    "transient_status",
    [
        status.HTTP_429_TOO_MANY_REQUESTS,
        status.HTTP_502_BAD_GATEWAY,
        status.HTTP_503_SERVICE_UNAVAILABLE,
        status.HTTP_504_GATEWAY_TIMEOUT,
    ],
)
async def test_complete_upload_retries_on_transient_server_error(
    aioresponses_mocker: aioresponses,
    session: ClientSession,
    completion_link: AnyUrl,
    transient_status: int,
):
    aioresponses_mocker.post(_COMPLETION_LINK, status=status.HTTP_202_ACCEPTED, payload=_COMPLETION_PAYLOAD)
    aioresponses_mocker.post(_STATE_LINK, status=transient_status)
    aioresponses_mocker.post(_STATE_LINK, status=status.HTTP_200_OK, payload=_STATE_OK_PAYLOAD)

    completed = await complete_upload(session, completion_link, [], is_directory=False)

    assert completed is not None
    assert completed.e_tag == _E_TAG


@pytest.mark.parametrize(
    "permanent_status",
    [
        status.HTTP_500_INTERNAL_SERVER_ERROR,
        status.HTTP_501_NOT_IMPLEMENTED,
    ],
)
async def test_complete_upload_does_not_retry_on_permanent_server_error(
    aioresponses_mocker: aioresponses,
    session: ClientSession,
    completion_link: AnyUrl,
    permanent_status: int,
):
    aioresponses_mocker.post(_COMPLETION_LINK, status=status.HTTP_202_ACCEPTED, payload=_COMPLETION_PAYLOAD)
    # NOTE: a single mock is registered, a retry would fail to match it
    aioresponses_mocker.post(_STATE_LINK, status=permanent_status)

    with pytest.raises(ClientResponseError) as exc_info:
        await complete_upload(session, completion_link, [], is_directory=False)

    assert exc_info.value.status == permanent_status


async def test_complete_upload_gives_up_on_persistent_transient_error(
    aioresponses_mocker: aioresponses,
    session: ClientSession,
    completion_link: AnyUrl,
):
    aioresponses_mocker.post(_COMPLETION_LINK, status=status.HTTP_202_ACCEPTED, payload=_COMPLETION_PAYLOAD)
    aioresponses_mocker.post(_STATE_LINK, status=status.HTTP_503_SERVICE_UNAVAILABLE, repeat=True)

    with pytest.raises(ClientResponseError) as exc_info:
        await complete_upload(session, completion_link, [], is_directory=False)

    assert exc_info.value.status == status.HTTP_503_SERVICE_UNAVAILABLE
