# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

from collections.abc import AsyncIterator, Iterator

import httpx
import pytest
import respx
from fastapi import status
from httpx import AsyncClient
from simcore_service_api_server.core.errors import BackendEnum, DirectorError


@pytest.fixture
def base_url() -> str:
    return f"https://{__name__}"


@pytest.fixture
def mock_server_api(base_url: str) -> Iterator[respx.MockRouter]:
    with respx.mock(
        base_url=base_url,
        assert_all_called=False,
        assert_all_mocked=True,  # IMPORTANT: KEEP always True!
    ) as mock:

        mock.get("/ok").respond(status.HTTP_200_OK)
        mock.post(path__startswith="/fail").respond(
            status.HTTP_500_INTERNAL_SERVER_ERROR, text="FAILURE"
        )

        yield mock


@pytest.fixture
async def client(
    mock_server_api: respx.MockRouter, base_url: str
) -> AsyncIterator[AsyncClient]:
    async with httpx.AsyncClient(base_url=base_url) as cli:
        yield cli


async def test_backend_error(client: AsyncClient):

    try:
        response = await client.post("/fail", params={"id": 3}, json={"x": 2})
        response.raise_for_status()

    except httpx.HTTPStatusError as err:

        service_error = DirectorError.from_httpx_status_error(err)

        assert hasattr(service_error, "http_status_error")  # auto-injected as context

        assert service_error.get_debug_message()
        assert service_error.service == BackendEnum.DIRECTOR
        assert (
            service_error.get_full_class_name()
            == "simcore_service_api_server.core.errors.BackendServiceError"
        )
