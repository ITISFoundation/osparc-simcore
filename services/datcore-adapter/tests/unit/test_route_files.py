# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

from typing import Dict, Any

import httpx
import pytest
from pydantic import parse_obj_as
from simcore_service_datcore_adapter.models.domains.files import FileDownloadOut
from starlette import status


@pytest.fixture
async def pennsieve_files_mock(pennsieve_subsystem_mock, pennsieve_file_id: str):
    mock = pennsieve_subsystem_mock
    if mock:
        FAKE_FILE_ID = "123434"
        # get packages files
        mock.get(url__regex=r"https://api.pennsieve.io/packages/.+/files$").respond(
            status.HTTP_200_OK,
            json=[{"content": {"size": 12345, "id": FAKE_FILE_ID}}],
        )
        # get presigned url
        mock.get(
            f"https://api.pennsieve.io/packages/{pennsieve_file_id}/files/{FAKE_FILE_ID}"
        ).respond(
            status.HTTP_200_OK,
            json={"url": "http://www.example.com/index.html"},
        )
    yield mock


@pytest.mark.asyncio
async def test_download_file_entrypoint(
    async_client: httpx.AsyncClient,
    pennsieve_client_mock: Any,
    pennsieve_subsystem_mock,
    pennsieve_files_mock,
    pennsieve_api_headers: Dict[str, str],
    pennsieve_file_id: str,
):
    file_id = pennsieve_file_id
    response = await async_client.get(
        f"v0/files/{file_id}",
        headers=pennsieve_api_headers,
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data
    parse_obj_as(FileDownloadOut, data)
