# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from unittest.mock import Mock

import httpx
from pydantic import parse_obj_as
from simcore_service_datcore_adapter.models.domains.files import FileDownloadOut
from starlette import status


async def test_download_file_entrypoint(
    async_client: httpx.AsyncClient,
    pennsieve_subsystem_mock: Mock,
    pennsieve_api_headers: dict[str, str],
    pennsieve_file_id: str,
):
    response = await async_client.get(
        f"v0/files/{pennsieve_file_id}",
        headers=pennsieve_api_headers,
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data
    parse_obj_as(FileDownloadOut, data)


async def test_delete_file_entrypoint(
    async_client: httpx.AsyncClient,
    pennsieve_subsystem_mock: Mock,
    pennsieve_api_headers: dict[str, str],
    pennsieve_file_id: str,
):
    response = await async_client.delete(
        f"v0/files/{pennsieve_file_id}",
        headers=pennsieve_api_headers,
    )
    assert response.status_code == status.HTTP_204_NO_CONTENT
    assert response.num_bytes_downloaded == 0
