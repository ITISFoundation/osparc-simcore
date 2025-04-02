# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=too-many-arguments
# pylint:disable=no-name-in-module
# pylint:disable=too-many-nested-blocks

import sys
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Literal

import httpx
import pytest
from faker import Faker
from fastapi import FastAPI
from models_library.api_schemas_storage.storage_schemas import (
    FileMetaDataGet,
)
from models_library.basic_types import SHA256Str
from models_library.projects import ProjectID
from models_library.projects_nodes_io import SimcoreS3FileID
from models_library.users import UserID
from models_library.utils.fastapi_encoders import jsonable_encoder
from pydantic import ByteSize, TypeAdapter
from pytest_simcore.helpers.fastapi import url_from_operation_id
from pytest_simcore.helpers.httpx_assert_checks import assert_status
from servicelib.aiohttp import status
from settings_library.s3 import S3Settings
from simcore_service_storage.models import SearchFilesQueryParams
from simcore_service_storage.simcore_s3_dsm import SimcoreS3DataManager

pytest_simcore_core_services_selection = ["postgres", "rabbit"]
pytest_simcore_ops_services_selection = ["adminer"]


CURRENT_DIR = Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent


async def test_simcore_s3_access_returns_default(
    initialized_app: FastAPI, client: httpx.AsyncClient
):
    url = url_from_operation_id(
        client, initialized_app, "get_or_create_temporary_s3_access"
    ).with_query(user_id=1)

    response = await client.post(f"{url}")
    received_settings, error = assert_status(response, status.HTTP_200_OK, S3Settings)
    assert not error
    assert received_settings


async def test_connect_to_external(
    set_log_levels_for_noisy_libraries: None,
    initialized_app: FastAPI,
    client: httpx.AsyncClient,
    user_id: UserID,
    project_id: ProjectID,
):
    url = url_from_operation_id(
        client,
        initialized_app,
        "list_files_metadata",
        location_id=f"{SimcoreS3DataManager.get_location_id()}",
    ).with_query(user_id=f"{user_id}", uuid_filter=f"{project_id}")
    resp = await client.get(f"{url}")
    data, error = assert_status(resp, status.HTTP_200_OK, list[FileMetaDataGet])
    print(data)


@pytest.fixture
async def uploaded_file_ids(
    faker: Faker,
    expected_number_of_user_files: int,
    upload_file: Callable[..., Awaitable[tuple[Path, SimcoreS3FileID]]],
) -> list[SimcoreS3FileID]:
    _files_ids_sorted_by_creation = []
    assert expected_number_of_user_files >= 0

    for _ in range(expected_number_of_user_files):
        file_path, file_id = await upload_file(
            file_size=TypeAdapter(ByteSize).validate_python("10Mib"),
            file_name=faker.file_name(),
            sha256_checksum=faker.sha256(),
        )
        assert file_path.exists()
        _files_ids_sorted_by_creation.append(file_id)

    return _files_ids_sorted_by_creation


@pytest.fixture
async def search_files_query_params(
    query_params_choice: str, user_id: UserID
) -> SearchFilesQueryParams:
    match query_params_choice:
        case "default":
            q = SearchFilesQueryParams(user_id=user_id, kind="owned")
        case "limited":
            q = SearchFilesQueryParams(user_id=user_id, kind="owned", limit=1)
        case "with_offset":
            q = SearchFilesQueryParams(user_id=user_id, kind="owned", offset=1)
        case _:
            pytest.fail(f"Undefined {query_params_choice=}")
    return q


@pytest.mark.parametrize(
    "location_id",
    [SimcoreS3DataManager.get_location_id()],
    ids=[SimcoreS3DataManager.get_location_name()],
    indirect=True,
)
@pytest.mark.parametrize("expected_number_of_user_files", [0, 1, 3])
@pytest.mark.parametrize("query_params_choice", ["default", "limited", "with_offset"])
async def test_search_files_request(
    initialized_app: FastAPI,
    client: httpx.AsyncClient,
    user_id: UserID,
    uploaded_file_ids: list[SimcoreS3FileID],
    query_params_choice: str,
    search_files_query_params: SearchFilesQueryParams,
):
    assert query_params_choice

    assert search_files_query_params.user_id == user_id
    url = url_from_operation_id(client, initialized_app, "search_files").with_query(
        jsonable_encoder(
            search_files_query_params, exclude_unset=True, exclude_none=True
        )
    )

    response = await client.post(f"{url}")
    found, error = assert_status(response, status.HTTP_200_OK, list[FileMetaDataGet])
    assert not error
    assert found is not None

    expected = uploaded_file_ids[
        search_files_query_params.offset : search_files_query_params.offset
        + search_files_query_params.limit
    ]
    assert [_.file_uuid for _ in found] == expected


@pytest.mark.parametrize(
    "location_id",
    [SimcoreS3DataManager.get_location_id()],
    ids=[SimcoreS3DataManager.get_location_name()],
    indirect=True,
)
@pytest.mark.parametrize("search_startswith", [True, False])
@pytest.mark.parametrize("search_sha256_checksum", [True, False])
@pytest.mark.parametrize("kind", ["owned", "read", None])
async def test_search_files(
    initialized_app: FastAPI,
    client: httpx.AsyncClient,
    user_id: UserID,
    upload_file: Callable[..., Awaitable[tuple[Path, SimcoreS3FileID]]],
    faker: Faker,
    search_startswith: bool,
    search_sha256_checksum: bool,
    kind: Literal["owned"],
):
    _file_name: str = faker.file_name()
    _sha256_checksum: SHA256Str = TypeAdapter(SHA256Str).validate_python(faker.sha256())

    url = url_from_operation_id(client, initialized_app, "search_files").with_query(
        jsonable_encoder(
            {
                "user_id": user_id,
                "kind": kind,
            },
            exclude_none=True,
        )
    )
    response = await client.post(f"{url}")

    if kind != "owned":
        assert_status(response, status.HTTP_422_UNPROCESSABLE_ENTITY, None)
        return

    list_fmds, error = assert_status(
        response, status.HTTP_200_OK, list[FileMetaDataGet]
    )
    assert not error
    assert not list_fmds

    # let's upload some files now
    file, file_id = await upload_file(
        file_size=TypeAdapter(ByteSize).validate_python("10Mib"),
        file_name=_file_name,
        sha256_checksum=_sha256_checksum,
    )
    # search again should return something
    response = await client.post(f"{url}")
    list_fmds, error = assert_status(
        response, status.HTTP_200_OK, list[FileMetaDataGet]
    )
    assert not error
    assert list_fmds
    assert len(list_fmds) == 1
    assert list_fmds[0].file_id == file_id
    assert list_fmds[0].file_size == file.stat().st_size
    assert list_fmds[0].sha256_checksum == _sha256_checksum

    # search again with part of the file uuid shall return the same
    if search_startswith:
        url.update_query(startswith=file_id[0:5])

    if search_sha256_checksum:
        url.update_query(sha256_checksum=_sha256_checksum)

    response = await client.post(f"{url}")
    list_fmds, error = assert_status(
        response, status.HTTP_200_OK, list[FileMetaDataGet]
    )
    assert not error
    assert list_fmds
    assert len(list_fmds) == 1
    assert list_fmds[0].file_id == file_id
    assert list_fmds[0].file_size == file.stat().st_size
    assert list_fmds[0].sha256_checksum == _sha256_checksum

    # search again with some other stuff shall return empty
    if search_startswith:
        url = url.update_query(startswith="Iamlookingforsomethingthatdoesnotexist")

    if search_sha256_checksum:
        dummy_sha256 = faker.sha256()
        while dummy_sha256 == _sha256_checksum:
            dummy_sha256 = faker.sha256()
        url = url.update_query(sha256_checksum=dummy_sha256)

    if search_startswith or search_sha256_checksum:
        response = await client.post(f"{url}")
        list_fmds, error = assert_status(
            response, status.HTTP_200_OK, list[FileMetaDataGet]
        )
        assert not error
        assert not list_fmds
