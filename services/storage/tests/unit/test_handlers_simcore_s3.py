# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=too-many-arguments
# pylint:disable=no-name-in-module
# pylint:disable=too-many-nested-blocks

import asyncio
import logging
import sys
from collections.abc import Awaitable, Callable
from copy import deepcopy
from pathlib import Path
from typing import Any, Literal

import httpx
import pytest
import sqlalchemy as sa
from aws_library.s3 import SimcoreS3API
from faker import Faker
from fastapi import FastAPI
from models_library.api_schemas_storage.storage_schemas import (
    FileMetaDataGet,
    FoldersBody,
)
from models_library.basic_types import SHA256Str
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID, NodeIDStr, SimcoreS3FileID
from models_library.users import UserID
from models_library.utils.fastapi_encoders import jsonable_encoder
from pydantic import ByteSize, TypeAdapter
from pytest_simcore.helpers.fastapi import url_from_operation_id
from pytest_simcore.helpers.httpx_assert_checks import assert_status
from pytest_simcore.helpers.logging_tools import log_context
from pytest_simcore.helpers.storage_utils import (
    FileIDDict,
    ProjectWithFilesParams,
    get_updated_project,
)
from pytest_simcore.helpers.storage_utils_file_meta_data import (
    assert_file_meta_data_in_db,
)
from pytest_simcore.helpers.storage_utils_project import clone_project_data
from pytest_simcore.helpers.typing_env import EnvVarsDict
from servicelib.aiohttp import status
from servicelib.fastapi.long_running_tasks.client import long_running_task_request
from settings_library.s3 import S3Settings
from simcore_postgres_database.storage_models import file_meta_data
from simcore_service_storage.models import SearchFilesQueryParams
from simcore_service_storage.simcore_s3_dsm import SimcoreS3DataManager
from sqlalchemy.ext.asyncio import AsyncEngine
from yarl import URL

pytest_simcore_core_services_selection = ["postgres"]
pytest_simcore_ops_services_selection = ["adminer", "minio"]


CURRENT_DIR = Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent


@pytest.fixture
def mock_datcore_download(mocker, client):
    # Use to mock downloading from DATCore
    async def _fake_download_to_file_or_raise(session, url, dest_path):
        with log_context(logging.INFO, f"Faking download:  {url} -> {dest_path}"):
            Path(dest_path).write_text(
                "FAKE: test_create_and_delete_folders_from_project"
            )

    mocker.patch(
        "simcore_service_storage.simcore_s3_dsm.download_to_file_or_raise",
        side_effect=_fake_download_to_file_or_raise,
        autospec=True,
    )

    mocker.patch(
        "simcore_service_storage.simcore_s3_dsm.datcore_adapter.get_file_download_presigned_link",
        autospec=True,
        return_value=URL("https://httpbin.org/image"),
    )


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


async def _request_copy_folders(
    initialized_app: FastAPI,
    client: httpx.AsyncClient,
    user_id: UserID,
    source_project: dict[str, Any],
    dst_project: dict[str, Any],
    nodes_map: dict[NodeID, NodeID],
) -> dict[str, Any]:
    url = url_from_operation_id(
        client, initialized_app, "copy_folders_from_project"
    ).with_query(user_id=user_id)

    with log_context(
        logging.INFO,
        f"Copying folders from {source_project['uuid']} to {dst_project['uuid']}",
    ) as ctx:
        async for lr_task in long_running_task_request(
            client,
            url,
            json=jsonable_encoder(
                FoldersBody(
                    source=source_project, destination=dst_project, nodes_map=nodes_map
                )
            ),
        ):
            ctx.logger.info("%s", f"<-- current state is {lr_task.progress=}")
            if lr_task.done():
                return await lr_task.result()

    pytest.fail(reason="Copy folders failed!")


async def test_copy_folders_from_non_existing_project(
    initialized_app: FastAPI,
    client: httpx.AsyncClient,
    user_id: UserID,
    create_project: Callable[[], Awaitable[dict[str, Any]]],
    faker: Faker,
):
    src_project = await create_project()
    incorrect_src_project = deepcopy(src_project)
    incorrect_src_project["uuid"] = faker.uuid4()
    dst_project = await create_project()
    incorrect_dst_project = deepcopy(dst_project)
    incorrect_dst_project["uuid"] = faker.uuid4()

    with pytest.raises(httpx.HTTPStatusError, match="404") as exc_info:
        await _request_copy_folders(
            initialized_app,
            client,
            user_id,
            incorrect_src_project,
            dst_project,
            nodes_map={},
        )
    assert_status(
        exc_info.value.response,
        status.HTTP_404_NOT_FOUND,
        None,
        expected_msg=f"{incorrect_src_project['uuid']} was not found",
    )

    with pytest.raises(httpx.HTTPStatusError, match="404") as exc_info:
        await _request_copy_folders(
            initialized_app,
            client,
            user_id,
            src_project,
            incorrect_dst_project,
            nodes_map={},
        )
    assert_status(
        exc_info.value.response,
        status.HTTP_404_NOT_FOUND,
        None,
        expected_msg=f"{incorrect_dst_project['uuid']} was not found",
    )


async def test_copy_folders_from_empty_project(
    initialized_app: FastAPI,
    client: httpx.AsyncClient,
    user_id: UserID,
    create_project: Callable[[], Awaitable[dict[str, Any]]],
    sqlalchemy_async_engine: AsyncEngine,
    storage_s3_client: SimcoreS3API,
):
    # we will copy from src to dst
    src_project = await create_project()
    dst_project = await create_project()

    data = await _request_copy_folders(
        initialized_app,
        client,
        user_id,
        src_project,
        dst_project,
        nodes_map={},
    )
    assert data == jsonable_encoder(dst_project)
    # check there is nothing in the dst project
    async with sqlalchemy_async_engine.connect() as conn:
        num_entries = await conn.scalar(
            sa.select(sa.func.count())
            .select_from(file_meta_data)
            .where(file_meta_data.c.project_id == dst_project["uuid"])
        )
        assert num_entries == 0


@pytest.fixture
def short_dsm_cleaner_interval(monkeypatch: pytest.MonkeyPatch) -> int:
    monkeypatch.setenv("STORAGE_CLEANER_INTERVAL_S", "1")
    return 1


@pytest.mark.parametrize(
    "project_params",
    [
        ProjectWithFilesParams(
            num_nodes=1,
            allowed_file_sizes=(TypeAdapter(ByteSize).validate_python("210Mib"),),
            allowed_file_checksums=(
                TypeAdapter(SHA256Str).validate_python(
                    "0b3216d95ec5a36c120ba16c88911dcf5ff655925d0fbdbc74cf95baf86de6fc"
                ),
            ),
            workspace_files_count=0,
        ),
    ],
    ids=str,
)
async def test_copy_folders_from_valid_project_with_one_large_file(
    initialized_app: FastAPI,
    short_dsm_cleaner_interval: int,
    client: httpx.AsyncClient,
    user_id: UserID,
    create_project: Callable[[], Awaitable[dict[str, Any]]],
    sqlalchemy_async_engine: AsyncEngine,
    random_project_with_files: Callable[
        [ProjectWithFilesParams],
        Awaitable[
            tuple[dict[str, Any], dict[NodeID, dict[SimcoreS3FileID, FileIDDict]]]
        ],
    ],
    project_params: ProjectWithFilesParams,
):
    # 1. create a src project with 1 large file
    src_project, src_projects_list = await random_project_with_files(project_params)
    # 2. create a dst project without files
    dst_project, nodes_map = clone_project_data(src_project)
    dst_project = await create_project(**dst_project)
    # copy the project files
    data = await _request_copy_folders(
        initialized_app,
        client,
        user_id,
        src_project,
        dst_project,
        nodes_map={NodeID(i): NodeID(j) for i, j in nodes_map.items()},
    )
    assert data == jsonable_encoder(
        await get_updated_project(sqlalchemy_async_engine, dst_project["uuid"])
    )
    # check that file meta data was effectively copied
    for src_node_id in src_projects_list:
        dst_node_id = nodes_map.get(
            TypeAdapter(NodeIDStr).validate_python(f"{src_node_id}")
        )
        assert dst_node_id
        for src_file_id, src_file in src_projects_list[src_node_id].items():
            path: Any = src_file["path"]
            assert isinstance(path, Path)
            checksum: Any = src_file["sha256_checksum"]
            assert isinstance(checksum, str)
            await assert_file_meta_data_in_db(
                sqlalchemy_async_engine,
                file_id=TypeAdapter(SimcoreS3FileID).validate_python(
                    f"{src_file_id}".replace(
                        f"{src_project['uuid']}", dst_project["uuid"]
                    ).replace(f"{src_node_id}", f"{dst_node_id}")
                ),
                expected_entry_exists=True,
                expected_file_size=path.stat().st_size,
                expected_upload_id=None,
                expected_upload_expiration_date=None,
                expected_sha256_checksum=TypeAdapter(SHA256Str).validate_python(
                    checksum
                ),
            )


@pytest.mark.parametrize(
    "project_params",
    [
        ProjectWithFilesParams(
            num_nodes=12,
            allowed_file_sizes=(
                TypeAdapter(ByteSize).validate_python("7Mib"),
                TypeAdapter(ByteSize).validate_python("110Mib"),
                TypeAdapter(ByteSize).validate_python("1Mib"),
            ),
            allowed_file_checksums=(
                TypeAdapter(SHA256Str).validate_python(
                    "311e2e130d83cfea9c3b7560699c221b0b7f9e5d58b02870bd52b695d8b4aabd"
                ),
                TypeAdapter(SHA256Str).validate_python(
                    "08e297db979d3c84f6b072c2a1e269e8aa04e82714ca7b295933a0c9c0f62b2e"
                ),
                TypeAdapter(SHA256Str).validate_python(
                    "488f3b57932803bbf644593bd46d95599b1d4da1d63bc020d7ebe6f1c255f7f3"
                ),
            ),
            workspace_files_count=0,
        ),
    ],
    ids=str,
)
async def test_copy_folders_from_valid_project(
    short_dsm_cleaner_interval: int,
    initialized_app: FastAPI,
    client: httpx.AsyncClient,
    user_id: UserID,
    create_project: Callable[[], Awaitable[dict[str, Any]]],
    create_simcore_file_id: Callable[[ProjectID, NodeID, str], SimcoreS3FileID],
    sqlalchemy_async_engine: AsyncEngine,
    random_project_with_files: Callable[
        [ProjectWithFilesParams],
        Awaitable[
            tuple[dict[str, Any], dict[NodeID, dict[SimcoreS3FileID, FileIDDict]]]
        ],
    ],
    project_params: ProjectWithFilesParams,
):
    # 1. create a src project with some files
    src_project, src_projects_list = await random_project_with_files(project_params)
    # 2. create a dst project without files
    dst_project, nodes_map = clone_project_data(src_project)
    dst_project = await create_project(**dst_project)
    # copy the project files
    data = await _request_copy_folders(
        initialized_app,
        client,
        user_id,
        src_project,
        dst_project,
        nodes_map={NodeID(i): NodeID(j) for i, j in nodes_map.items()},
    )
    assert data == jsonable_encoder(
        await get_updated_project(sqlalchemy_async_engine, dst_project["uuid"])
    )

    # check that file meta data was effectively copied
    for src_node_id in src_projects_list:
        dst_node_id = nodes_map.get(
            TypeAdapter(NodeIDStr).validate_python(f"{src_node_id}")
        )
        assert dst_node_id
        for src_file_id, src_file in src_projects_list[src_node_id].items():
            path: Any = src_file["path"]
            assert isinstance(path, Path)
            checksum: Any = src_file["sha256_checksum"]
            assert isinstance(checksum, str)
            await assert_file_meta_data_in_db(
                sqlalchemy_async_engine,
                file_id=TypeAdapter(SimcoreS3FileID).validate_python(
                    f"{src_file_id}".replace(
                        f"{src_project['uuid']}", dst_project["uuid"]
                    ).replace(f"{src_node_id}", f"{dst_node_id}")
                ),
                expected_entry_exists=True,
                expected_file_size=path.stat().st_size,
                expected_upload_id=None,
                expected_upload_expiration_date=None,
                expected_sha256_checksum=TypeAdapter(SHA256Str).validate_python(
                    checksum
                ),
            )


async def _create_and_delete_folders_from_project(
    user_id: UserID,
    project: dict[str, Any],
    initialized_app: FastAPI,
    client: httpx.AsyncClient,
    project_db_creator: Callable,
    check_list_files: bool,
) -> None:
    destination_project, nodes_map = clone_project_data(project)
    await project_db_creator(**destination_project)

    # creating a copy
    data = await _request_copy_folders(
        initialized_app,
        client,
        user_id,
        project,
        destination_project,
        nodes_map={NodeID(i): NodeID(j) for i, j in nodes_map.items()},
    )

    # data should be equal to the destination project, and all store entries should point to simcore.s3
    # NOTE: data is jsonized where destination project is not!
    assert jsonable_encoder(destination_project) == data

    project_id = data["uuid"]

    # list data to check all is here

    if check_list_files:
        url = url_from_operation_id(
            client,
            initialized_app,
            "list_files_metadata",
            location_id=f"{SimcoreS3DataManager.get_location_id()}",
        ).with_query(user_id=f"{user_id}", uuid_filter=f"{project_id}")

        resp = await client.get(f"{url}")
        data, error = assert_status(resp, status.HTTP_200_OK, list[FileMetaDataGet])
        assert not error
    # DELETING
    url = url_from_operation_id(
        client,
        initialized_app,
        "delete_folders_of_project",
        folder_id=project_id,
    ).with_query(user_id=f"{user_id}")
    resp = await client.delete(f"{url}")
    assert_status(resp, status.HTTP_204_NO_CONTENT, None)

    # list data is gone
    if check_list_files:
        url = url_from_operation_id(
            client,
            initialized_app,
            "list_files_metadata",
            location_id=f"{SimcoreS3DataManager.get_location_id()}",
        ).with_query(user_id=f"{user_id}", uuid_filter=f"{project_id}")
        resp = await client.get(f"{url}")
        data, error = assert_status(resp, status.HTTP_200_OK, list[FileMetaDataGet])
        assert not error
        assert not data


@pytest.fixture
def set_log_levels_for_noisy_libraries() -> None:
    # Reduce the log level for 'werkzeug'
    logging.getLogger("werkzeug").setLevel(logging.WARNING)


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


@pytest.mark.parametrize(
    "project_params",
    [
        ProjectWithFilesParams(
            num_nodes=3,
            allowed_file_sizes=(
                TypeAdapter(ByteSize).validate_python("7Mib"),
                TypeAdapter(ByteSize).validate_python("110Mib"),
                TypeAdapter(ByteSize).validate_python("1Mib"),
            ),
            workspace_files_count=0,
        )
    ],
)
async def test_create_and_delete_folders_from_project(
    set_log_levels_for_noisy_libraries: None,
    initialized_app: FastAPI,
    client: httpx.AsyncClient,
    user_id: UserID,
    create_project: Callable[..., Awaitable[dict[str, Any]]],
    with_random_project_with_files: tuple[
        dict[str, Any],
        dict[NodeID, dict[SimcoreS3FileID, dict[str, Path | str]]],
    ],
    mock_datcore_download,
):
    project_in_db, _ = with_random_project_with_files
    await _create_and_delete_folders_from_project(
        user_id,
        project_in_db,
        initialized_app,
        client,
        create_project,
        check_list_files=True,
    )


@pytest.mark.parametrize(
    "project_params",
    [
        ProjectWithFilesParams(
            num_nodes=3,
            allowed_file_sizes=(
                TypeAdapter(ByteSize).validate_python("7Mib"),
                TypeAdapter(ByteSize).validate_python("110Mib"),
                TypeAdapter(ByteSize).validate_python("1Mib"),
            ),
            workspace_files_count=0,
        )
    ],
)
@pytest.mark.parametrize("num_concurrent_calls", [50])
async def test_create_and_delete_folders_from_project_burst(
    set_log_levels_for_noisy_libraries: None,
    minio_s3_settings_envs: EnvVarsDict,
    initialized_app: FastAPI,
    client: httpx.AsyncClient,
    user_id: UserID,
    with_random_project_with_files: tuple[
        dict[str, Any],
        dict[NodeID, dict[SimcoreS3FileID, dict[str, Path | str]]],
    ],
    create_project: Callable[..., Awaitable[dict[str, Any]]],
    mock_datcore_download,
    num_concurrent_calls: int,
):
    project_in_db, _ = with_random_project_with_files
    # NOTE: here the point is to NOT have a limit on the number of calls!!
    await asyncio.gather(
        *[
            _create_and_delete_folders_from_project(
                user_id,
                project_in_db,
                initialized_app,
                client,
                create_project,
                check_list_files=False,
            )
            for _ in range(num_concurrent_calls)
        ]
    )


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
