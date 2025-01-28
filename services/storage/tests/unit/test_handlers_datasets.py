# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=too-many-arguments
# pylint:disable=no-name-in-module


from collections.abc import Awaitable, Callable
from pathlib import Path

import pytest
from faker import Faker
from fastapi import FastAPI
from httpx import AsyncClient
from models_library.api_schemas_storage import DatasetMetaDataGet, FileMetaDataGet
from models_library.projects import ProjectID
from models_library.projects_nodes_io import SimcoreS3FileID
from models_library.users import UserID
from pydantic import ByteSize, TypeAdapter
from pytest_mock import MockerFixture
from pytest_simcore.helpers.fastapi import url_from_operation_id
from pytest_simcore.helpers.parametrizations import (
    byte_size_ids,
    parametrized_file_size,
)
from servicelib.aiohttp import status
from yarl import URL

pytest_simcore_core_services_selection = ["postgres"]
pytest_simcore_ops_services_selection = ["adminer"]


async def test_list_dataset_files_metadata_with_no_files_returns_empty_array(
    initialized_app: FastAPI,
    client: AsyncClient,
    user_id: UserID,
    project_id: ProjectID,
    location_id: int,
):
    url = url_from_operation_id(
        client,
        initialized_app,
        "list_datasets_metadata",
        location_id=location_id,
        project_id=project_id,
    ).with_query(user_id=user_id)

    response = await client.get(f"{url}")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data == []


@pytest.mark.parametrize(
    "file_size",
    [parametrized_file_size("100Mib")],
    ids=byte_size_ids,
)
async def test_list_dataset_files_metadata(
    upload_file: Callable[[ByteSize, str], Awaitable[tuple[Path, SimcoreS3FileID]]],
    client: AsyncClient,
    user_id: UserID,
    project_id: ProjectID,
    location_id: int,
    file_size: ByteSize,
    faker: Faker,
):
    NUM_FILES = 3
    for n in range(NUM_FILES):
        file, file_id = await upload_file(file_size, faker.file_name())
        url = URL(
            f"/v0/locations/{location_id}/datasets/{project_id}/metadata"
        ).with_query(user_id=user_id)

        response = await client.get(f"{url}")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data
        list_fmds = TypeAdapter(list[FileMetaDataGet]).validate_python(data)
        assert len(list_fmds) == (n + 1)
        fmd = list_fmds[n]
        assert fmd.file_name == file.name
        assert fmd.file_id == file_id
        assert fmd.file_uuid == file_id
        assert fmd.file_size == file.stat().st_size


async def test_list_datasets_metadata(
    client: AsyncClient,
    user_id: UserID,
    location_id: int,
    project_id: ProjectID,
):
    url = URL(f"/v0/locations/{location_id}/datasets").with_query(user_id=user_id)

    response = await client.get(f"{url}")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data
    list_datasets = TypeAdapter(list[DatasetMetaDataGet]).validate_python(data)
    assert len(list_datasets) == 1
    dataset = list_datasets[0]
    assert dataset.dataset_id == project_id


async def test_ensure_expand_dirs_defaults_true(
    mocker: MockerFixture,
    client: AsyncClient,
    user_id: UserID,
    project_id: ProjectID,
    location_id: int,
):
    mocked_object = mocker.patch(
        "simcore_service_storage.simcore_s3_dsm.SimcoreS3DataManager.list_files_in_dataset",
        autospec=True,
    )

    url = URL(f"/v0/locations/{location_id}/datasets/{project_id}/metadata").with_query(
        user_id=user_id
    )

    await client.get(f"{url}")

    assert len(mocked_object.call_args_list) == 1
    call_args_list = mocked_object.call_args_list[0]
    assert "expand_dirs" in call_args_list.kwargs
    assert call_args_list.kwargs["expand_dirs"] is True
