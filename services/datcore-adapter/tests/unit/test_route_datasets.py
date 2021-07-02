# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

from pathlib import Path
from typing import Dict, List

import httpx
import pytest
from fastapi_pagination import Page
from pydantic import parse_obj_as
from simcore_service_datcore_adapter.models.schemas.datasets import (
    DatasetMetaData,
    FileMetaData,
)
from starlette import status

pytestmark = pytest.mark.asyncio


async def test_list_datasets_entrypoint(
    async_client: httpx.AsyncClient,
    pennsieve_subsystem_mock,
    pennsieve_api_headers: Dict[str, str],
):
    response = await async_client.get(
        "v0/datasets",
        headers=pennsieve_api_headers,
    )

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data
    parse_obj_as(Page[DatasetMetaData], data)


async def test_list_dataset_files_legacy_entrypoint(
    async_client: httpx.AsyncClient,
    pennsieve_dataset_id: str,
    pennsieve_subsystem_mock,
    pennsieve_api_headers: Dict[str, str],
):
    dataset_id = pennsieve_dataset_id

    response = await async_client.get(
        f"v0/datasets/{dataset_id}/files_legacy",
        headers=pennsieve_api_headers,
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data
    parse_obj_as(List[FileMetaData], data)


async def test_list_dataset_top_level_files_entrypoint(
    async_client: httpx.AsyncClient,
    pennsieve_dataset_id: str,
    pennsieve_subsystem_mock,
    pennsieve_api_headers: Dict[str, str],
):
    dataset_id = pennsieve_dataset_id

    response = await async_client.get(
        f"v0/datasets/{dataset_id}/files",
        headers=pennsieve_api_headers,
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data
    parse_obj_as(Page[FileMetaData], data)


async def test_list_dataset_collection_files_entrypoint(
    async_client: httpx.AsyncClient,
    pennsieve_dataset_id: str,
    pennsieve_collection_id: str,
    pennsieve_subsystem_mock,
    pennsieve_api_headers: Dict[str, str],
):
    dataset_id = pennsieve_dataset_id
    collection_id = pennsieve_collection_id

    response = await async_client.get(
        f"v0/datasets/{dataset_id}/files/{collection_id}",
        headers=pennsieve_api_headers,
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data
    parse_obj_as(Page[FileMetaData], data)


# FIXME: one issue: the client had a header Content-Type: application/json, and the file was empty, to be tested again
@pytest.mark.skip(reason="unable to make the httpx client work with fastapi.")
async def test_upload_file_in_dataset_entrypoint(
    async_client: httpx.AsyncClient,
    pennsieve_dataset_id: str,
    # pennsieve_subsystem_mock,
    pennsieve_api_headers: Dict[str, str],
    tmp_path: Path,
):
    async with httpx.AsyncClient() as client:

        # create some temp file
        file_to_upload = tmp_path / "file_to_upload_to_pennsieve.txt"
        file_to_upload.write_bytes(b"\x01" * 1024)
        # headers = {"Content-Type": "multipart/form-data"}
        headers = {}
        headers.update(pennsieve_api_headers)
        dataset_id = pennsieve_dataset_id
        response = await client.post(
            # f"v0/datasets/{dataset_id}/files",
            "http://httpbin.org/anything",
            headers=headers,
            files={
                "file": file_to_upload.open("rb"),
            },
        )
