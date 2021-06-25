# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

from typing import Dict

import httpx
import pytest
from pydantic import parse_obj_as
from simcore_service_datcore_adapter.models.domains.files import FileDownloadOut
from starlette import status


@pytest.mark.asyncio
async def test_download_file_entrypoint(
    async_client: httpx.AsyncClient,
    pennsieve_api_headers: Dict[str, str],
):
    file_id = "N:package:09c142c4-d013-4431-b266-aa1c563105b0"
    response = await async_client.get(
        f"v0/files/{file_id}",
        headers=pennsieve_api_headers,
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data
    parse_obj_as(FileDownloadOut, data)
