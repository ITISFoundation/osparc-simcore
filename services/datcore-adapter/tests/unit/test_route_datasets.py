# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name


from typing import Optional

import httpx
import respx
from fastapi_pagination import Page
from pydantic import parse_obj_as
from simcore_service_datcore_adapter.models.schemas.datasets import (
    DatasetMetaData,
    FileMetaData,
)
from starlette import status


async def test_list_datasets_entrypoint(
    async_client: httpx.AsyncClient,
    pennsieve_subsystem_mock: Optional[respx.MockRouter],
    pennsieve_api_headers: dict[str, str],
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
    pennsieve_api_headers: dict[str, str],
):
    dataset_id = pennsieve_dataset_id

    response = await async_client.get(
        f"v0/datasets/{dataset_id}/files_legacy",
        headers=pennsieve_api_headers,
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data
    parse_obj_as(list[FileMetaData], data)


async def test_list_dataset_top_level_files_entrypoint(
    async_client: httpx.AsyncClient,
    pennsieve_dataset_id: str,
    pennsieve_subsystem_mock,
    pennsieve_api_headers: dict[str, str],
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
    pennsieve_api_headers: dict[str, str],
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
