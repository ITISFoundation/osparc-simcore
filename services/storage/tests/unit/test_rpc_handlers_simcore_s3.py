# pylint:disable=no-name-in-module
# pylint:disable=protected-access
# pylint:disable=redefined-outer-name
# pylint:disable=too-many-arguments
# pylint:disable=too-many-positional-arguments
# pylint:disable=unused-argument
# pylint:disable=unused-variable

import asyncio
import datetime
import logging
import re
from collections.abc import Awaitable, Callable
from copy import deepcopy
from pathlib import Path
from typing import Any, Literal
from unittest.mock import Mock

import httpx
import pytest
import sqlalchemy as sa
from celery.contrib.testing.worker import TestWorkController
from celery_library.task_manager import CeleryTaskManager
from faker import Faker
from fastapi import FastAPI
from fastapi.encoders import jsonable_encoder
from models_library.api_schemas_rpc_async_jobs.async_jobs import AsyncJobResult
from models_library.api_schemas_rpc_async_jobs.exceptions import JobError
from models_library.api_schemas_storage import STORAGE_RPC_NAMESPACE
from models_library.api_schemas_storage.storage_schemas import (
    FileMetaDataGet,
    FoldersBody,
    PresignedLink,
)
from models_library.api_schemas_webserver.storage import PathToExport
from models_library.basic_types import SHA256Str
from models_library.products import ProductName
from models_library.projects_nodes_io import NodeID, SimcoreS3FileID
from models_library.users import UserID
from pydantic import ByteSize, TypeAdapter
from pytest_mock import MockerFixture
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
from servicelib.aiohttp import status
from servicelib.rabbitmq._client_rpc import RabbitMQRPCClient
from servicelib.rabbitmq._errors import RPCServerError
from servicelib.rabbitmq.rpc_interfaces.async_jobs.async_jobs import wait_and_get_result
from servicelib.rabbitmq.rpc_interfaces.storage.simcore_s3 import (
    copy_folders_from_project,
    start_export_data,
)
from simcore_postgres_database.storage_models import file_meta_data
from simcore_service_storage.simcore_s3_dsm import SimcoreS3DataManager
from sqlalchemy.ext.asyncio import AsyncEngine
from yarl import URL

pytest_simcore_core_services_selection = ["postgres", "rabbit"]
pytest_simcore_ops_services_selection = ["adminer"]


async def _request_copy_folders(
    rpc_client: RabbitMQRPCClient,
    user_id: UserID,
    product_name: ProductName,
    src_project: dict[str, Any],
    src_project_nodes: dict[NodeID, dict[str, Any]],
    dst_project: dict[str, Any],
    dst_project_nodes: dict[NodeID, dict[str, Any]],
    nodes_map: dict[NodeID, NodeID],
    *,
    client_timeout: datetime.timedelta = datetime.timedelta(seconds=60),
) -> dict[str, Any]:
    with log_context(
        logging.INFO,
        f"Copying folders from {src_project['uuid']} to {dst_project['uuid']}",
    ) as ctx:
        source = src_project | {
            "workbench": {
                f"{node_id}": node for node_id, node in src_project_nodes.items()
            }
        }
        destination = dst_project | {
            "workbench": {
                f"{node_id}": node for node_id, node in dst_project_nodes.items()
            }
        }

        async_job_get, async_job_name = await copy_folders_from_project(
            rpc_client,
            user_id=user_id,
            product_name=product_name,
            body=FoldersBody(
                source=source, destination=destination, nodes_map=nodes_map
            ),
        )

        async for async_job_result in wait_and_get_result(
            rpc_client,
            rpc_namespace=STORAGE_RPC_NAMESPACE,
            method_name=copy_folders_from_project.__name__,
            job_id=async_job_get.job_id,
            job_filter=async_job_name,
            client_timeout=client_timeout,
        ):
            ctx.logger.info("%s", f"<-- current state is {async_job_result=}")
            if async_job_result.done:
                result = await async_job_result.result()
                assert isinstance(result, AsyncJobResult)
                return result.result

    pytest.fail(reason="Copy folders failed!")


async def test_copy_folders_from_non_existing_project(
    initialized_app: FastAPI,
    storage_rabbitmq_rpc_client: RabbitMQRPCClient,
    user_id: UserID,
    product_name: ProductName,
    create_project: Callable[..., Awaitable[dict[str, Any]]],
    faker: Faker,
    with_storage_celery_worker: TestWorkController,
):
    src_project = await create_project()
    incorrect_src_project = deepcopy(src_project)
    incorrect_src_project["uuid"] = faker.uuid4()
    dst_project = await create_project()
    incorrect_dst_project = deepcopy(dst_project)
    incorrect_dst_project["uuid"] = faker.uuid4()

    with pytest.raises(
        JobError, match=f"Project {incorrect_src_project['uuid']} was not found"
    ):
        await _request_copy_folders(
            storage_rabbitmq_rpc_client,
            user_id,
            product_name,
            incorrect_src_project,
            {},
            dst_project,
            {},
            nodes_map={},
        )

    with pytest.raises(
        JobError, match=f"Project {incorrect_dst_project['uuid']} was not found"
    ):
        await _request_copy_folders(
            storage_rabbitmq_rpc_client,
            user_id,
            product_name,
            src_project,
            {},
            incorrect_dst_project,
            {},
            nodes_map={},
        )


async def test_copy_folders_from_empty_project(
    initialized_app: FastAPI,
    storage_rabbitmq_rpc_client: RabbitMQRPCClient,
    user_id: UserID,
    product_name: ProductName,
    create_project: Callable[[], Awaitable[dict[str, Any]]],
    sqlalchemy_async_engine: AsyncEngine,
    with_storage_celery_worker: TestWorkController,
):
    # we will copy from src to dst
    src_project = await create_project()
    dst_project = await create_project()

    data = await _request_copy_folders(
        storage_rabbitmq_rpc_client,
        user_id,
        product_name,
        src_project,
        {},
        dst_project,
        {},
        nodes_map={},
    )
    data.pop("workbench", None)  # remove workbench from the data
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
    "location_id",
    [SimcoreS3DataManager.get_location_id()],
    ids=[SimcoreS3DataManager.get_location_name()],
    indirect=True,
)
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
    storage_rabbitmq_rpc_client: RabbitMQRPCClient,
    user_id: UserID,
    product_name: ProductName,
    create_project: Callable[[], Awaitable[dict[str, Any]]],
    sqlalchemy_async_engine: AsyncEngine,
    random_project_with_files: Callable[
        [ProjectWithFilesParams],
        Awaitable[
            tuple[
                dict[str, Any],
                dict[NodeID, dict[str, Any]],
                dict[NodeID, dict[SimcoreS3FileID, FileIDDict]],
            ]
        ],
    ],
    project_params: ProjectWithFilesParams,
):
    # 1. create a src project with 1 large file
    src_project, src_project_nodes, src_projects_list = await random_project_with_files(
        project_params
    )
    # 2. create a dst project without files
    dst_project, dst_project_nodes, nodes_map = clone_project_data(
        src_project, src_project_nodes
    )
    dst_project = await create_project(**dst_project)

    data = await _request_copy_folders(
        storage_rabbitmq_rpc_client,
        user_id,
        product_name,
        src_project,
        src_project_nodes,
        dst_project,
        dst_project_nodes,
        nodes_map=nodes_map,
    )
    data.pop("workbench", None)  # remove workbench from the data
    assert data == jsonable_encoder(
        await get_updated_project(sqlalchemy_async_engine, dst_project["uuid"])
    )
    # check that file meta data was effectively copied
    for src_node_id in src_projects_list:
        dst_node_id = nodes_map.get(src_node_id)
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
    "location_id",
    [SimcoreS3DataManager.get_location_id()],
    ids=[SimcoreS3DataManager.get_location_name()],
    indirect=True,
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
    storage_rabbitmq_rpc_client: RabbitMQRPCClient,
    user_id: UserID,
    product_name: ProductName,
    create_project: Callable[[], Awaitable[dict[str, Any]]],
    sqlalchemy_async_engine: AsyncEngine,
    random_project_with_files: Callable[
        [ProjectWithFilesParams],
        Awaitable[
            tuple[
                dict[str, Any],
                dict[NodeID, dict[str, Any]],
                dict[NodeID, dict[SimcoreS3FileID, FileIDDict]],
            ]
        ],
    ],
    project_params: ProjectWithFilesParams,
):
    # 1. create a src project with some files
    src_project, src_project_nodes, src_projects_list = await random_project_with_files(
        project_params
    )
    # 2. create a dst project without files
    dst_project, dst_project_nodes, nodes_map = clone_project_data(
        src_project, src_project_nodes
    )
    dst_project = await create_project(**dst_project)
    # copy the project files
    data = await _request_copy_folders(
        storage_rabbitmq_rpc_client,
        user_id,
        product_name,
        src_project,
        src_project_nodes,
        dst_project,
        dst_project_nodes,
        nodes_map=nodes_map,
    )
    data.pop("workbench", None)  # remove workbench from the data
    assert data == jsonable_encoder(
        await get_updated_project(sqlalchemy_async_engine, dst_project["uuid"])
    )

    # check that file meta data was effectively copied
    for src_node_id in src_projects_list:
        dst_node_id = nodes_map.get(src_node_id)
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
    rpc_client: RabbitMQRPCClient,
    client: httpx.AsyncClient,
    user_id: UserID,
    product_name: ProductName,
    project: dict[str, Any],
    project_nodes: dict[NodeID, dict[str, Any]],
    initialized_app: FastAPI,
    project_db_creator: Callable,
    check_list_files: bool,
    *,
    client_timeout: datetime.timedelta = datetime.timedelta(seconds=60),
) -> None:
    dst_project, dst_project_nodes, nodes_map = clone_project_data(
        project, project_nodes
    )
    await project_db_creator(**dst_project)

    # creating a copy
    data = await _request_copy_folders(
        rpc_client,
        user_id,
        product_name,
        project,
        project_nodes,
        dst_project,
        dst_project_nodes,
        nodes_map=nodes_map,
        client_timeout=client_timeout,
    )

    data.pop("workbench", None)  # remove workbench from the data

    # data should be equal to the destination project, and all store entries should point to simcore.s3
    # NOTE: data is jsonized where destination project is not!
    assert jsonable_encoder(dst_project) == data

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
def mock_datcore_download(mocker: MockerFixture, client: httpx.AsyncClient) -> None:
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


@pytest.mark.parametrize(
    "location_id",
    [SimcoreS3DataManager.get_location_id()],
    ids=[SimcoreS3DataManager.get_location_name()],
    indirect=True,
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
@pytest.mark.parametrize("num_concurrent_calls", [1], ids=str)
async def test_create_and_delete_folders_from_project(
    set_log_levels_for_noisy_libraries: None,
    initialized_app: FastAPI,
    storage_rabbitmq_rpc_client: RabbitMQRPCClient,
    client: httpx.AsyncClient,
    user_id: UserID,
    product_name: ProductName,
    with_random_project_with_files: tuple[
        dict[str, Any],
        dict[NodeID, dict[str, Any]],
        dict[NodeID, dict[SimcoreS3FileID, dict[str, Path | str]]],
    ],
    create_project: Callable[..., Awaitable[dict[str, Any]]],
    mock_datcore_download,
    num_concurrent_calls: int,
):
    project_in_db, project_nodes_in_db, _ = with_random_project_with_files
    # NOTE: here the point is to NOT have a limit on the number of calls!!
    await asyncio.gather(
        *[
            _create_and_delete_folders_from_project(
                storage_rabbitmq_rpc_client,
                client,
                user_id,
                product_name,
                project_in_db,
                project_nodes_in_db,
                initialized_app,
                create_project,
                check_list_files=False,
                client_timeout=datetime.timedelta(seconds=300),
            )
            for _ in range(num_concurrent_calls)
        ]
    )


async def _request_start_export_data(
    rpc_client: RabbitMQRPCClient,
    user_id: UserID,
    product_name: ProductName,
    paths_to_export: list[PathToExport],
    export_as: Literal["path", "download_link"],
    *,
    client_timeout: datetime.timedelta = datetime.timedelta(seconds=60),
) -> str:
    with log_context(
        logging.INFO,
        f"Data export form {paths_to_export=}",
    ) as ctx:
        async_job_get, async_job_name = await start_export_data(
            rpc_client,
            user_id=user_id,
            product_name=product_name,
            paths_to_export=paths_to_export,
            export_as=export_as,
        )

        async for async_job_result in wait_and_get_result(
            rpc_client,
            rpc_namespace=STORAGE_RPC_NAMESPACE,
            method_name=start_export_data.__name__,
            job_id=async_job_get.job_id,
            job_filter=async_job_name,
            client_timeout=client_timeout,
        ):
            ctx.logger.info("%s", f"<-- current state is {async_job_result=}")
            if async_job_result.done:
                result = await async_job_result.result()
                assert isinstance(result, AsyncJobResult)
                return result.result

    pytest.fail(reason="data export failed!")


@pytest.fixture
def task_progress_spy(mocker: MockerFixture) -> Mock:
    return mocker.spy(CeleryTaskManager, "set_task_progress")


@pytest.mark.parametrize(
    "location_id",
    [SimcoreS3DataManager.get_location_id()],
    ids=[SimcoreS3DataManager.get_location_name()],
    indirect=True,
)
@pytest.mark.parametrize(
    "project_params",
    [
        ProjectWithFilesParams(
            num_nodes=4,
            allowed_file_sizes=(TypeAdapter(ByteSize).validate_python("1KiB"),),
            allowed_file_checksums=(
                TypeAdapter(SHA256Str).validate_python(
                    "0b3216d95ec5a36c120ba16c88911dcf5ff655925d0fbdbc74cf95baf86de6fc"
                ),
            ),
            workspace_files_count=10,
        ),
    ],
    ids=str,
)
@pytest.mark.parametrize(
    "export_as",
    ["path", "download_link"],
)
async def test_start_export_data(
    initialized_app: FastAPI,
    short_dsm_cleaner_interval: int,
    with_storage_celery_worker: TestWorkController,
    storage_rabbitmq_rpc_client: RabbitMQRPCClient,
    user_id: UserID,
    product_name: ProductName,
    create_project: Callable[[], Awaitable[dict[str, Any]]],
    sqlalchemy_async_engine: AsyncEngine,
    random_project_with_files: Callable[
        [ProjectWithFilesParams],
        Awaitable[
            tuple[
                dict[str, Any],
                dict[NodeID, dict[str, Any]],
                dict[NodeID, dict[SimcoreS3FileID, FileIDDict]],
            ]
        ],
    ],
    project_params: ProjectWithFilesParams,
    task_progress_spy: Mock,
    export_as: Literal["path", "download_link"],
):
    _, _, src_projects_list = await random_project_with_files(project_params)

    all_available_files: set[SimcoreS3FileID] = set()
    for x in src_projects_list.values():
        all_available_files |= x.keys()

    nodes_in_project_to_export = {
        TypeAdapter(PathToExport).validate_python("/".join(Path(x).parts[0:2]))
        for x in all_available_files
    }

    result = await _request_start_export_data(
        storage_rabbitmq_rpc_client,
        user_id,
        product_name,
        paths_to_export=list(nodes_in_project_to_export),
        export_as=export_as,
    )

    if export_as == "path":
        assert re.fullmatch(
            rf"^exports/{user_id}/[0-9a-fA-F]{{8}}-[0-9a-fA-F]{{4}}-[0-9a-fA-F]{{4}}-[0-9a-fA-F]{{4}}-[0-9a-fA-F]{{12}}\.zip$",
            result,
        )
    elif export_as == "download_link":
        link = PresignedLink.model_validate(result).link
        assert re.search(
            rf"exports/{user_id}/[0-9a-fA-F]{{8}}-[0-9a-fA-F]{{4}}-[0-9a-fA-F]{{4}}-[0-9a-fA-F]{{4}}-[0-9a-fA-F]{{12}}\.zip",
            f"{link}",
        )
    else:
        pytest.fail(f"Unexpected export_as value: {export_as}")

    progress_updates = [x[0][2].actual_value for x in task_progress_spy.call_args_list]
    assert progress_updates[0] == 0
    assert progress_updates[-1] == 1


@pytest.mark.parametrize(
    "export_as",
    ["path", "download_link"],
)
async def test_start_export_data_access_error(
    initialized_app: FastAPI,
    short_dsm_cleaner_interval: int,
    with_storage_celery_worker: TestWorkController,
    storage_rabbitmq_rpc_client: RabbitMQRPCClient,
    user_id: UserID,
    product_name: ProductName,
    faker: Faker,
    export_as: Literal["path", "download_link"],
):
    path_to_export = TypeAdapter(PathToExport).validate_python(
        f"{faker.uuid4()}/{faker.uuid4()}/{faker.file_name()}"
    )
    with pytest.raises(JobError) as exc:
        await _request_start_export_data(
            storage_rabbitmq_rpc_client,
            user_id,
            product_name,
            paths_to_export=[path_to_export],
            client_timeout=datetime.timedelta(seconds=60),
            export_as=export_as,
        )

    assert isinstance(exc.value, JobError)
    assert exc.value.exc_type == "AccessRightError"
    assert f" {user_id} " in f"{exc.value}"
    assert f" {path_to_export} " in f"{exc.value}"


async def test_start_export_invalid_export_format(
    initialized_app: FastAPI,
    short_dsm_cleaner_interval: int,
    with_storage_celery_worker: TestWorkController,
    storage_rabbitmq_rpc_client: RabbitMQRPCClient,
    user_id: UserID,
    product_name: ProductName,
    faker: Faker,
):
    path_to_export = TypeAdapter(PathToExport).validate_python(
        f"{faker.uuid4()}/{faker.uuid4()}/{faker.file_name()}"
    )
    with pytest.raises(RPCServerError) as exc:
        await _request_start_export_data(
            storage_rabbitmq_rpc_client,
            user_id,
            product_name,
            paths_to_export=[path_to_export],
            client_timeout=datetime.timedelta(seconds=60),
            export_as="invalid_format",  # type: ignore
        )

    assert exc.value.exc_type == "builtins.ValueError"
