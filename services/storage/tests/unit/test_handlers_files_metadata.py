# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument


import urllib.parse
from collections.abc import Awaitable, Callable
from pathlib import Path
from random import choice

import pytest
from aiohttp.test_utils import TestClient
from faker import Faker
from models_library.api_schemas_storage import FileMetaDataGet, SimcoreS3FileID
from models_library.projects import ProjectID
from models_library.users import UserID
from pydantic import ByteSize, parse_obj_as
from pytest_simcore.helpers.utils_assert import assert_status
from servicelib.aiohttp import status

pytest_simcore_core_services_selection = ["postgres"]
pytest_simcore_ops_services_selection = ["adminer"]


async def test_get_files_metadata(
    upload_file: Callable[[ByteSize, str], Awaitable[tuple[Path, SimcoreS3FileID]]],
    client: TestClient,
    user_id: UserID,
    location_id: int,
    project_id: ProjectID,
    faker: Faker,
):
    assert client.app

    url = (
        client.app.router["get_files_metadata"]
        .url_for(location_id=f"{location_id}")
        .with_query(user_id=f"{user_id}")
    )

    # this should return an empty list
    response = await client.get(f"{url}")
    data, error = await assert_status(response, status.HTTP_200_OK)
    assert not error
    list_fmds = parse_obj_as(list[FileMetaDataGet], data)
    assert not list_fmds

    # now add some stuff there
    NUM_FILES = 10
    file_size = parse_obj_as(ByteSize, "15Mib")
    files_owned_by_us = []
    for _ in range(NUM_FILES):
        files_owned_by_us.append(await upload_file(file_size, faker.file_name()))
    # we should find these files now
    response = await client.get(f"{url}")
    data, error = await assert_status(response, status.HTTP_200_OK)
    assert not error
    list_fmds = parse_obj_as(list[FileMetaDataGet], data)
    assert len(list_fmds) == NUM_FILES
    # create some more files but with a base common name
    NUM_FILES = 10
    file_size = parse_obj_as(ByteSize, "15Mib")
    files_with_common_name = []
    for _ in range(NUM_FILES):
        files_with_common_name.append(
            await upload_file(file_size, f"common_name-{faker.file_name()}")
        )
    # we should find these files now
    response = await client.get(f"{url}")
    data, error = await assert_status(response, status.HTTP_200_OK)
    assert not error
    list_fmds = parse_obj_as(list[FileMetaDataGet], data)
    assert len(list_fmds) == (2 * NUM_FILES)
    # we can filter them now
    response = await client.get(f"{url.update_query(uuid_filter='common_name')}")
    data, error = await assert_status(response, status.HTTP_200_OK)
    assert not error
    list_fmds = parse_obj_as(list[FileMetaDataGet], data)
    assert len(list_fmds) == (NUM_FILES)


@pytest.mark.xfail(
    reason="storage get_file_metadata must return a 200 with no payload as long as legacy services are around!!"
)
async def test_get_file_metadata_is_legacy_services_compatible(
    client: TestClient,
    user_id: UserID,
    location_id: int,
    simcore_file_id: SimcoreS3FileID,
):
    assert client.app

    url = (
        client.app.router["get_file_metadata"]
        .url_for(
            location_id=f"{location_id}",
            file_id=f"{urllib.parse.quote(simcore_file_id, safe='')}",
        )
        .with_query(user_id=f"{user_id}")
    )
    # this should return an empty list
    response = await client.get(f"{url}")
    await assert_status(response, status.HTTP_404_NOT_FOUND)


async def test_get_file_metadata(
    upload_file: Callable[[ByteSize, str], Awaitable[tuple[Path, SimcoreS3FileID]]],
    client: TestClient,
    user_id: UserID,
    location_id: int,
    project_id: ProjectID,
    simcore_file_id: SimcoreS3FileID,
    faker: Faker,
):
    assert client.app

    url = (
        client.app.router["get_file_metadata"]
        .url_for(
            location_id=f"{location_id}",
            file_id=f"{urllib.parse.quote(simcore_file_id, safe='')}",
        )
        .with_query(user_id=f"{user_id}")
    )
    # this should return an empty list
    response = await client.get(f"{url}")
    # await assert_status(response, status.HTTP_404_NOT_FOUND)

    # NOTE: This needs to be a Ok response with empty data until ALL legacy services are gone, then it should be changed to 404! see test above
    assert response.status == status.HTTP_200_OK
    assert await response.json() == {"data": {}, "error": "No result found"}

    # now add some stuff there
    NUM_FILES = 10
    file_size = parse_obj_as(ByteSize, "15Mib")
    files_owned_by_us = []
    for _ in range(NUM_FILES):
        files_owned_by_us.append(await upload_file(file_size, faker.file_name()))
    selected_file, selected_file_uuid = choice(files_owned_by_us)
    url = (
        client.app.router["get_file_metadata"]
        .url_for(
            location_id=f"{location_id}",
            file_id=f"{urllib.parse.quote(selected_file_uuid, safe='')}",
        )
        .with_query(user_id=f"{user_id}")
    )
    response = await client.get(f"{url}")
    data, error = await assert_status(response, status.HTTP_200_OK)
    assert not error
    assert data
    fmd = parse_obj_as(FileMetaDataGet, data)
    assert fmd.file_id == selected_file_uuid
    assert fmd.file_size == selected_file.stat().st_size
