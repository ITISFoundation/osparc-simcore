# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

from collections import namedtuple
from typing import Any, Callable, Dict, List, Optional, Tuple, Type

import faker
import httpx
import pytest
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
) -> List[Type[Tuple]]:
    datasets = [ps_dataset(pennsieve_fake_dataset_id(), fake.text()) for _ in range(10)]
    return datasets


@pytest.mark.asyncio
async def test_list_datasets_entrypoint(
    async_client: httpx.AsyncClient,
    pennsieve_client_mock: Optional[Any],
    pennsieve_random_fake_datasets: List[Type[Tuple]],
    pennsieve_api_headers: Dict[str, str],
):
    if pennsieve_client_mock:
        pennsieve_client_mock.return_value.datasets.return_value = (
            pennsieve_random_fake_datasets
        )
    response = await async_client.get(
        "v0/datasets",
        headers=pennsieve_api_headers,
    )

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data
    parse_obj_as(Page[DatasetMetaData], data)


@pytest.mark.asyncio
async def test_list_dataset_files_legacy_entrypoint(
    async_client: httpx.AsyncClient,
    pennsieve_dataset_id: str,
    pennsieve_client_mock: Optional[Any],
    pennsieve_mock_dataset_packages: Dict[str, Any],
    pennsieve_api_headers: Dict[str, str],
):
    dataset_id = pennsieve_dataset_id
    if pennsieve_client_mock:
        # pylint: disable=protected-access
        pennsieve_client_mock.return_value.get_dataset.return_value._api.datasets._get.return_value = (
            pennsieve_mock_dataset_packages
        )

    response = await async_client.get(
        f"v0/datasets/{dataset_id}/files_legacy",
        headers=pennsieve_api_headers,
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data
    parse_obj_as(List[FileMetaData], data)
