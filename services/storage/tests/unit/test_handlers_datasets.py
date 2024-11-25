# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=too-many-arguments
# pylint:disable=no-name-in-module


from collections.abc import Awaitable, Callable
from pathlib import Path

import pytest
from aiohttp.test_utils import TestClient
from faker import Faker
from models_library.api_schemas_storage import DatasetMetaDataGet, FileMetaDataGet
from models_library.projects import ProjectID
from models_library.projects_nodes_io import SimcoreS3FileID
from models_library.users import UserID
from pydantic import ByteSize, TypeAdapter
from pytest_mock import MockerFixture
from pytest_simcore.helpers.assert_checks import assert_status
from pytest_simcore.helpers.parametrizations import (
    byte_size_ids,
    parametrized_file_size,
)
from servicelib.aiohttp import status

pytest_simcore_core_services_selection = ["postgres"]
pytest_simcore_ops_services_selection = ["adminer"]


async def test_get_files_metadata_dataset_with_no_files_returns_empty_array(
    client: TestClient,
    user_id: UserID,
    project_id: ProjectID,
    location_id: int,
):
    assert client.app
    url = (
        client.app.router["get_files_metadata_dataset"]
        .url_for(location_id=f"{location_id}", dataset_id=f"{project_id}")
        .with_query(user_id=user_id)
    )
    response = await client.get(f"{url}")
    data, error = await assert_status(response, status.HTTP_200_OK)
    assert data == []
    assert not error


@pytest.mark.parametrize(
    "file_size",
    [parametrized_file_size("100Mib")],
    ids=byte_size_ids,
)
async def test_get_files_metadata_dataset(
    upload_file: Callable[[ByteSize, str], Awaitable[tuple[Path, SimcoreS3FileID]]],
    client: TestClient,
    user_id: UserID,
    project_id: ProjectID,
    location_id: int,
    file_size: ByteSize,
    faker: Faker,
):
    assert client.app
    NUM_FILES = 3
    for n in range(NUM_FILES):
        file, file_id = await upload_file(file_size, faker.file_name())
        url = (
            client.app.router["get_files_metadata_dataset"]
            .url_for(location_id=f"{location_id}", dataset_id=f"{project_id}")
            .with_query(user_id=user_id)
        )
        response = await client.get(f"{url}")
        data, error = await assert_status(response, status.HTTP_200_OK)
        assert data
        assert not error
        list_fmds = TypeAdapter(list[FileMetaDataGet]).validate_python(data)
        assert len(list_fmds) == (n + 1)
        fmd = list_fmds[n]
        assert fmd.file_name == file.name
        assert fmd.file_id == file_id
        assert fmd.file_uuid == file_id
        assert fmd.file_size == file.stat().st_size


async def test_get_datasets_metadata(
    client: TestClient,
    user_id: UserID,
    location_id: int,
    project_id: ProjectID,
):
    assert client.app

    url = (
        client.app.router["get_datasets_metadata"]
        .url_for(location_id=f"{location_id}")
        .with_query(user_id=f"{user_id}")
    )

    response = await client.get(f"{url}")
    data, error = await assert_status(response, status.HTTP_200_OK)
    assert data
    assert not error
    list_datasets = TypeAdapter(list[DatasetMetaDataGet]).validate_python(data)
    assert len(list_datasets) == 1
    dataset = list_datasets[0]
    assert dataset.dataset_id == project_id


async def test_ensure_expand_dirs_defaults_true(
    mocker: MockerFixture,
    client: TestClient,
    user_id: UserID,
    project_id: ProjectID,
    location_id: int,
):
    mocked_object = mocker.patch(
        "simcore_service_storage.simcore_s3_dsm.SimcoreS3DataManager.list_files_in_dataset",
        autospec=True,
    )

    assert client.app
    url = (
        client.app.router["get_files_metadata_dataset"]
        .url_for(location_id=f"{location_id}", dataset_id=f"{project_id}")
        .with_query(user_id=user_id)
    )
    await client.get(f"{url}")

    assert len(mocked_object.call_args_list) == 1
    call_args_list = mocked_object.call_args_list[0]
    assert "expand_dirs" in call_args_list.kwargs
    assert call_args_list.kwargs["expand_dirs"] is True
