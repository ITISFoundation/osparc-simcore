# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

from typing import Dict, Any
import faker

import httpx
import pytest
from pydantic import parse_obj_as
from simcore_service_datcore_adapter.models.domains.files import FileDownloadOut
from starlette import status


@pytest.mark.asyncio
async def test_download_file_entrypoint(
    async_client: httpx.AsyncClient,
    pennsieve_client_mock: Any,
    pennsieve_data_package_mock: Any,
    pennsieve_file_package_mock: Any,
    pennsieve_api_headers: Dict[str, str],
    pennsieve_file_id: str,
):
    if pennsieve_client_mock:
        pennsieve_client_mock.return_value.get.return_value = (
            pennsieve_data_package_mock
        )
        pennsieve_data_package_mock.files = [pennsieve_file_package_mock]
        pennsieve_file_package_mock.url = faker.Faker().url()

    file_id = pennsieve_file_id
    response = await async_client.get(
        f"v0/files/{file_id}",
        headers=pennsieve_api_headers,
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data
    parse_obj_as(FileDownloadOut, data)
