# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import json
from collections import namedtuple
from pathlib import Path
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
def pennsieve_fake_dataset_id() -> Callable:
    def creator() -> str:
        return f"N:dataset:{uuid4()}"

    return creator


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


@pytest.fixture(scope="session")
def pennsieve_mock_dataset_packages(mocks_dir: Path) -> Dict[str, Any]:
    ps_packages_file = mocks_dir / "ps_packages.json"
    assert ps_packages_file.exists()
    return json.loads(ps_packages_file.read_text())


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
