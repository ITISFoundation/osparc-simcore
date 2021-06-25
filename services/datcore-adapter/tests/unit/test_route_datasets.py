# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

from collections import namedtuple
from typing import Any, Callable, Dict, List, Tuple, Type

import faker
import httpx
import pytest
from pydantic import parse_obj_as
from simcore_service_datcore_adapter.models.schemas.datasets import (
    DatasetMetaData,
    FileMetaData,
)
from starlette import status

fake = faker.Faker()

ps_dataset = namedtuple("ps_dataset", "id,name")


@pytest.fixture()
def pennsieve_random_fake_datasets(
    pennsieve_client_mock: Any, pennsieve_fake_dataset_id: Callable
) -> List[Type[Tuple]]:
    datasets = [ps_dataset(pennsieve_fake_dataset_id(), fake.text()) for _ in range(10)]
    return datasets


@pytest.fixture()
def pennsieve_datasets_mock(pennsieve_client_mock: Any) -> Callable:
    def mock_datasets(fake_ps_datasets: List[Tuple]):
        pennsieve_client_mock.return_value.datasets.return_value = fake_ps_datasets

    return mock_datasets


@pytest.mark.asyncio
async def test_list_datasets_entrypoint(
    async_client: httpx.AsyncClient,
    pennsieve_datasets_mock: Callable,
    pennsieve_random_fake_datasets: List[Type[Tuple]],
    pennsieve_api_headers: Dict[str, str],
):
    pennsieve_datasets_mock(pennsieve_random_fake_datasets)
    response = await async_client.get(
        "v0/datasets",
        headers=pennsieve_api_headers,
    )

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data
    parse_obj_as(List[DatasetMetaData], data)


@pytest.mark.asyncio
async def test_list_dataset_files_entrypoint(
    async_client: httpx.AsyncClient,
    pennsieve_fake_dataset_id: Callable,
    pennsieve_client_mock: Any,
    pennsieve_mock_dataset_packages: Dict[str, Any],
    pennsieve_api_headers: Dict[str, str],
):
    dataset_id = pennsieve_fake_dataset_id()
    # pylint: disable=protected-access
    pennsieve_client_mock.return_value.get_dataset.return_value._api.datasets._get.return_value = (
        pennsieve_mock_dataset_packages
    )

    # dataset_id = "N:dataset:6b29ddff-86fc-4dc3-bb78-8e572a788a85"
    response = await async_client.get(
        f"v0/datasets/{dataset_id}/files",
        headers=pennsieve_api_headers,
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data
    parse_obj_as(List[FileMetaData], data)
