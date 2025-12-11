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
from models_library.api_schemas_storage.storage_schemas import (
    DatasetMetaDataGet,
    FileMetaDataGet,
)
from models_library.projects import ProjectID
from models_library.projects_nodes_io import LocationID, SimcoreS3FileID
from models_library.users import UserID
from pydantic import ByteSize
from pytest_mock import MockerFixture
from pytest_simcore.helpers.fastapi import url_from_operation_id
from pytest_simcore.helpers.httpx_assert_checks import assert_status
from pytest_simcore.helpers.parametrizations import (
    byte_size_ids,
    parametrized_file_size,
)
from servicelib.aiohttp import status
from simcore_service_storage.simcore_s3_dsm import SimcoreS3DataManager

pytest_simcore_core_services_selection = ["postgres", "rabbit"]
pytest_simcore_ops_services_selection = ["adminer"]


async def test_list_dataset_files_metadata_with_no_files_returns_empty_array(
    initialized_app: FastAPI,
    client: AsyncClient,
    user_id: UserID,
    project_id: ProjectID,
    location_id: LocationID,
    fake_datcore_tokens: tuple[str, str],
):
    url = url_from_operation_id(
        client,
        initialized_app,
        "list_dataset_files_metadata",
        location_id=location_id,
        dataset_id=project_id,
    ).with_query(user_id=user_id)

    response = await client.get(f"{url}")
    data, error = assert_status(response, status.HTTP_200_OK, list[FileMetaDataGet])
    assert data == []
    assert not error


@pytest.mark.parametrize(
    "location_id",
    [SimcoreS3DataManager.get_location_id()],
    ids=[SimcoreS3DataManager.get_location_name()],
    indirect=True,
)
@pytest.mark.parametrize(
    "file_size",
    [parametrized_file_size("100Mib")],
    ids=byte_size_ids,
)
async def test_list_dataset_files_metadata(
    upload_file: Callable[[ByteSize, str], Awaitable[tuple[Path, SimcoreS3FileID]]],
    initialized_app: FastAPI,
    client: AsyncClient,
    user_id: UserID,
    project_id: ProjectID,
    location_id: LocationID,
    file_size: ByteSize,
    faker: Faker,
):
    NUM_FILES = 3
    for n in range(NUM_FILES):
        file, file_id = await upload_file(file_size, faker.file_name())
        url = url_from_operation_id(
            client,
            initialized_app,
            "list_dataset_files_metadata",
            location_id=location_id,
            dataset_id=project_id,
        ).with_query(user_id=user_id)

        response = await client.get(f"{url}")
        list_fmds, error = assert_status(
            response, status.HTTP_200_OK, list[FileMetaDataGet]
        )
        assert not error
        assert list_fmds
        assert len(list_fmds) == (n + 1)
        fmd = list_fmds[n]
        assert fmd.file_name == file.name
        assert fmd.file_id == file_id
        assert fmd.file_uuid == file_id
        assert fmd.file_size == file.stat().st_size


@pytest.mark.parametrize(
    "location_id",
    [SimcoreS3DataManager.get_location_id()],
    ids=[SimcoreS3DataManager.get_location_name()],
    indirect=True,
)
async def test_list_datasets_metadata(
    initialized_app: FastAPI,
    client: AsyncClient,
    user_id: UserID,
    location_id: LocationID,
    project_id: ProjectID,
):
    url = url_from_operation_id(
        client,
        initialized_app,
        "list_datasets_metadata",
        location_id=location_id,
    ).with_query(user_id=user_id)

    response = await client.get(f"{url}")
    list_datasets, error = assert_status(
        response, status.HTTP_200_OK, list[DatasetMetaDataGet]
    )
    assert response.status_code == status.HTTP_200_OK
    assert list_datasets
    assert len(list_datasets) == 1
    dataset = list_datasets[0]
    assert dataset.dataset_id == project_id


@pytest.mark.parametrize(
    "location_id",
    [SimcoreS3DataManager.get_location_id()],
    ids=[SimcoreS3DataManager.get_location_name()],
    indirect=True,
)
async def test_ensure_expand_dirs_defaults_true(
    mocker: MockerFixture,
    initialized_app: FastAPI,
    client: AsyncClient,
    user_id: UserID,
    project_id: ProjectID,
    location_id: LocationID,
):
    mocked_object = mocker.patch(
        "simcore_service_storage.simcore_s3_dsm.SimcoreS3DataManager.list_files_in_dataset",
        autospec=True,
    )

    url = url_from_operation_id(
        client,
        initialized_app,
        "list_dataset_files_metadata",
        location_id=location_id,
        dataset_id=project_id,
    ).with_query(user_id=user_id)

    await client.get(f"{url}")

    assert len(mocked_object.call_args_list) == 1
    call_args_list = mocked_object.call_args_list[0]
    assert "expand_dirs" in call_args_list.kwargs
    assert call_args_list.kwargs["expand_dirs"] is True
