# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from unittest.mock import Mock

import httpx
from pydantic import TypeAdapter
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
    TypeAdapter(FileDownloadOut).validate_python(data)


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


async def test_package_file_entrypoint(
    async_client: httpx.AsyncClient,
    pennsieve_subsystem_mock: Mock,
    pennsieve_api_headers: dict[str, str],
    pennsieve_file_id: str,
):
    response = await async_client.get(
        f"v0/packages/{pennsieve_file_id}/files",
        headers=pennsieve_api_headers,
        params={"limit": 1, "offset": 0},
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data
    assert len(data) == 1
