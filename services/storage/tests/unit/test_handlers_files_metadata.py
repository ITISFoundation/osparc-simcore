# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument


from collections.abc import Awaitable, Callable
from copy import deepcopy
from pathlib import Path
from random import choice
from typing import Protocol

import httpx
import pytest
from faker import Faker
from fastapi import FastAPI
from models_library.projects import ProjectID
from models_library.storage_schemas import FileMetaDataGet, SimcoreS3FileID
from models_library.users import UserID
from pydantic import ByteSize, TypeAdapter
from pytest_simcore.helpers.fastapi import url_from_operation_id
from pytest_simcore.helpers.httpx_assert_checks import assert_status
from servicelib.aiohttp import status
from yarl import URL

pytest_simcore_core_services_selection = ["postgres"]
pytest_simcore_ops_services_selection = ["adminer"]


class CreateProjectAccessRightsCallable(Protocol):
    async def __call__(
        self,
        project_id: ProjectID,
        user_id: UserID,
        read: bool,
        write: bool,
        delete: bool,
    ) -> None:
        ...


async def test_list_files_metadata(
    upload_file: Callable[[ByteSize, str], Awaitable[tuple[Path, SimcoreS3FileID]]],
    create_project_access_rights: CreateProjectAccessRightsCallable,
    initialized_app: FastAPI,
    client: httpx.AsyncClient,
    user_id: UserID,
    other_user_id: UserID,
    location_id: int,
    project_id: ProjectID,
    faker: Faker,
):
    url = (
        URL(f"{client.base_url}")
        .with_path(
            initialized_app.url_path_for("list_files_metadata", location_id=location_id)
        )
        .with_query(user_id=f"{user_id}")
    )

    # this should return an empty list
    response = await client.get(f"{url}")

    list_fmds, error = assert_status(
        response, status.HTTP_200_OK, list[FileMetaDataGet]
    )
    assert list_fmds == []
    assert not error

    # now add some stuff there
    NUM_FILES = 10
    file_size = TypeAdapter(ByteSize).validate_python("15Mib")
    files_owned_by_us = [
        await upload_file(file_size, faker.file_name()) for _ in range(NUM_FILES)
    ]
    assert files_owned_by_us

    # we should find these files now
    response = await client.get(f"{url}")
    list_fmds, error = assert_status(
        response, status.HTTP_200_OK, list[FileMetaDataGet]
    )
    assert list_fmds
    assert not error
    assert len(list_fmds) == NUM_FILES

    # checks project_id filter!
    await create_project_access_rights(
        project_id=project_id,
        user_id=other_user_id,
        read=True,
        write=True,
        delete=True,
    )
    previous_data = deepcopy(list_fmds)
    response = await client.get(
        f"{url.update_query(project_id=str(project_id), user_id=other_user_id)}"
    )

    list_fmds, error = assert_status(
        response, status.HTTP_200_OK, list[FileMetaDataGet]
    )
    assert list_fmds
    assert not error
    assert len(list_fmds) == (NUM_FILES)
    assert previous_data == list_fmds

    # create some more files but with a base common name
    NUM_FILES = 10
    file_size = TypeAdapter(ByteSize).validate_python("15Mib")
    files_with_common_name = [
        await upload_file(file_size, f"common_name-{faker.file_name()}")
        for _ in range(NUM_FILES)
    ]
    assert files_with_common_name

    # we should find these files now
    response = await client.get(f"{url}")
    list_fmds, error = assert_status(
        response, status.HTTP_200_OK, list[FileMetaDataGet]
    )
    assert list_fmds
    assert not error
    assert len(list_fmds) == (2 * NUM_FILES)

    # we can filter them now
    response = await client.get(f"{url.update_query(uuid_filter='common_name')}")
    list_fmds, error = assert_status(
        response, status.HTTP_200_OK, list[FileMetaDataGet]
    )
    assert list_fmds
    assert not error
    assert len(list_fmds) == (NUM_FILES)


@pytest.mark.xfail(
    reason="storage get_file_metadata must return a 200 with no payload as long as legacy services are around!!"
)
async def test_get_file_metadata_is_legacy_services_compatible(
    initialized_app: FastAPI,
    client: httpx.AsyncClient,
    user_id: UserID,
    location_id: int,
    simcore_file_id: SimcoreS3FileID,
):
    url = (
        URL(f"{client.base_url}")
        .with_path(
            initialized_app.url_path_for(
                "get_file_metadata",
                location_id=location_id,
                file_id=simcore_file_id,
            )
        )
        .with_query(user_id=f"{user_id}")
    )

    # this should return an empty list
    response = await client.get(f"{url}")
    assert response.status_code == status.HTTP_404_NOT_FOUND


async def test_get_file_metadata(
    upload_file: Callable[[ByteSize, str], Awaitable[tuple[Path, SimcoreS3FileID]]],
    initialized_app: FastAPI,
    client: httpx.AsyncClient,
    user_id: UserID,
    location_id: int,
    project_id: ProjectID,
    simcore_file_id: SimcoreS3FileID,
    faker: Faker,
):
    url = url_from_operation_id(
        client,
        initialized_app,
        "get_file_metadata",
        location_id=f"{location_id}",
        file_id=simcore_file_id,
    ).with_query(user_id=user_id)

    # this should return an empty list
    response = await client.get(f"{url}")
    # await assert_status(response, status.HTTP_404_NOT_FOUND)

    # NOTE: This needs to be a Ok response with empty data until ALL legacy services are gone, then it should be changed to 404! see test above
    data, error = assert_status(response, status.HTTP_200_OK, dict)
    assert error == "No result found"
    assert data == {}

    # now add some stuff there
    NUM_FILES = 10
    file_size = TypeAdapter(ByteSize).validate_python("15Mib")
    files_owned_by_us = [
        await upload_file(file_size, faker.file_name()) for _ in range(NUM_FILES)
    ]
    selected_file, selected_file_uuid = choice(files_owned_by_us)  # noqa: S311
    url = url_from_operation_id(
        client,
        initialized_app,
        "get_file_metadata",
        location_id=f"{location_id}",
        file_id=selected_file_uuid,
    ).with_query(user_id=user_id)

    response = await client.get(f"{url}")
    fmd, error = assert_status(response, status.HTTP_200_OK, FileMetaDataGet)
    assert not error
    assert fmd
    assert fmd.file_id == selected_file_uuid
    assert fmd.file_size == selected_file.stat().st_size
