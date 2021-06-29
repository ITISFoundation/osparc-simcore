# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

from collections import namedtuple
from typing import Any, Callable, Dict, List, Optional, Tuple, Type

import faker
import httpx
from pydantic.networks import url_regex
import pytest
import respx
from fastapi_pagination import Page
from pydantic import parse_obj_as
from simcore_service_datcore_adapter.models.schemas.datasets import (
    DatasetMetaData,
    FileMetaData,
)
from starlette import status

fake = faker.Faker()

ps_dataset = namedtuple("ps_dataset", "id,name")


@pytest.fixture(scope="module")
def pennsieve_random_fake_datasets(
    pennsieve_fake_dataset_id: Callable,
) -> Dict[str, Any]:
    datasets = {
        "datasets": [
            {"content": {"id": pennsieve_fake_dataset_id(), "name": fake.text()}}
            for _ in range(10)
        ],
        "totalCount": 20,
    }
    return datasets


@pytest.fixture()
async def pennsieve_datasets_paginated_mock(
    pennsieve_client_mock, pennsieve_random_fake_datasets
):
    if pennsieve_client_mock:
        async with respx.mock as mock:
            mock.get("https://api.pennsieve.io/datasets/paginated").respond(
                status.HTTP_200_OK, json=pennsieve_random_fake_datasets
            )
            yield
    else:
        yield


@pytest.mark.asyncio
async def test_list_datasets_entrypoint(
    async_client: httpx.AsyncClient,
    pennsieve_datasets_paginated_mock: None,
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


@pytest.fixture()
async def pennsieve_datasets_legacy_mock(
    pennsieve_client_mock,
    pennsieve_mock_dataset_packages,
    pennsieve_dataset_id: str,
    pennsieve_collection_id: str,
):
    if pennsieve_client_mock:
        async with respx.mock as mock:
            mock.get(
                f"https://api.pennsieve.io/datasets/{pennsieve_dataset_id}/packageTypeCounts"
            ).respond(
                status.HTTP_200_OK,
                json={"part1": len(pennsieve_mock_dataset_packages["packages"])},
            )
            mock.get(
                f"https://api.pennsieve.io/datasets/{pennsieve_dataset_id}"
            ).respond(
                status.HTTP_200_OK,
                json={
                    "content": {"name": "Some dataset name that is awesome"},
                    "children": pennsieve_mock_dataset_packages["packages"],
                },
            )
            mock.get(
                f"https://api.pennsieve.io/datasets/{pennsieve_dataset_id}/packages"
            ).respond(status.HTTP_200_OK, json=pennsieve_mock_dataset_packages)

            mock.get(
                f"https://api.pennsieve.io/packages/{pennsieve_collection_id}"
            ).respond(
                status.HTTP_200_OK,
                json={
                    "content": {"name": "this package name is also awesome"},
                    "children": pennsieve_mock_dataset_packages["packages"],
                    "ancestors": [
                        {"content": {"name": "Bigger guy"}},
                        {"content": {"name": "Big guy"}},
                    ],
                },
            )

            mock.get(url__regex=r"https://api.pennsieve.io/packages/.+/files").respond(
                status.HTTP_200_OK, json=[{"content": {"size": 12345}}]
            )
            yield
    else:
        yield


@pytest.mark.asyncio
async def test_list_dataset_files_legacy_entrypoint(
    async_client: httpx.AsyncClient,
    pennsieve_dataset_id: str,
    pennsieve_datasets_legacy_mock: None,
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


@pytest.mark.asyncio
async def test_list_dataset_top_level_files_entrypoint(
    async_client: httpx.AsyncClient,
    pennsieve_dataset_id: str,
    pennsieve_datasets_legacy_mock: None,
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


@pytest.mark.asyncio
async def test_list_dataset_collection_files_entrypoint(
    async_client: httpx.AsyncClient,
    pennsieve_dataset_id: str,
    pennsieve_collection_id: str,
    pennsieve_datasets_legacy_mock: None,
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
