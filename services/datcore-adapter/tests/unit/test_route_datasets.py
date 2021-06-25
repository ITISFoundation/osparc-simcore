# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

from collections import namedtuple
from typing import Any, Callable, Dict, List, Tuple, Type
from uuid import uuid4

import faker
import httpx
import pytest
from pydantic import parse_obj_as
from simcore_service_datcore_adapter.models.schemas.datasets import (
    DatasetMetaData,
    FileMetaData,
)
from starlette import status


@pytest.fixture()
def pennsieve_client_mock(
    mocker, pennsieve_api_key: str, pennsieve_api_secret: str
) -> Any:
    ps_mock = mocker.patch(
        "simcore_service_datcore_adapter.modules.pennsieve.Pennsieve", autospec=True
    )
    yield ps_mock

    ps_mock.assert_any_call(
        api_secret=pennsieve_api_secret, api_token=pennsieve_api_key
    )


fake = faker.Faker()

ps_dataset = namedtuple("ps_dataset", "id,name")


@pytest.fixture(scope="session")
def pennsieve_dataset_id() -> Callable:
    def creator() -> str:
        return f"N:dataset:{uuid4()}"

    return creator


@pytest.fixture()
def pennsieve_random_fake_datasets(
    pennsieve_client_mock: Any, pennsieve_dataset_id: Callable
) -> List[Type[Tuple]]:
    datasets = [ps_dataset(pennsieve_dataset_id(), fake.text()) for _ in range(10)]
    return datasets


@pytest.fixture()
def pennsieve_get_datasets_mock(pennsieve_client_mock: Any) -> Callable:
    def mock_datasets(fake_ps_datasets: List[Tuple]):
        pennsieve_client_mock.return_value.datasets.return_value = fake_ps_datasets

    return mock_datasets


@pytest.mark.asyncio
async def test_list_datasets_entrypoint(
    async_client: httpx.AsyncClient,
    pennsieve_get_datasets_mock: Callable,
    pennsieve_random_fake_datasets: List[Type[Tuple]],
    pennsieve_api_headers: Dict[str, str],
):
    pennsieve_get_datasets_mock(pennsieve_random_fake_datasets)
    response = await async_client.get(
        "v0/datasets",
        headers=pennsieve_api_headers,
    )

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data
    parsed_objects = parse_obj_as(List[DatasetMetaData], data)
    for parsed_object, ps_dataset in zip(
        parsed_objects, pennsieve_random_fake_datasets
    ):
        assert parsed_object.id == ps_dataset.id
        assert parsed_object.display_name == ps_dataset.name


@pytest.mark.asyncio
async def test_list_dataset_files_entrypoint(
    async_client: httpx.AsyncClient,
    pennsieve_dataset_id: Callable,
    # pennsieve_get_datasets_mock: Callable,
    pennsieve_api_headers: Dict[str, str],
):
    dataset_id = "N:dataset:6b29ddff-86fc-4dc3-bb78-8e572a788a85"
    dataset_id = "N:dataset:ea2325d8-46d7-4fbd-a644-30f6433070b4"
    response = await async_client.get(
        f"v0/datasets/{dataset_id}/files",
        headers=pennsieve_api_headers,
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data
    parse_obj_as(List[FileMetaData], data)
