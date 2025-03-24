import datetime
import logging
from collections.abc import Awaitable, Callable
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest
import sqlalchemy as sa
from aws_library.s3 import SimcoreS3API
from faker import Faker
from fastapi import FastAPI
from fastapi.encoders import jsonable_encoder
from models_library.api_schemas_rpc_async_jobs.async_jobs import AsyncJobResult
from models_library.api_schemas_storage import STORAGE_RPC_NAMESPACE
from models_library.api_schemas_storage.storage_schemas import FoldersBody
from models_library.basic_types import SHA256Str
from models_library.projects_nodes_io import NodeID, NodeIDStr, SimcoreS3FileID
from models_library.users import UserID
from pydantic import ByteSize, TypeAdapter
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
from servicelib.rabbitmq._client_rpc import RabbitMQRPCClient
from servicelib.rabbitmq.rpc_interfaces.async_jobs.async_jobs import wait_and_get_result
from servicelib.rabbitmq.rpc_interfaces.storage.simcore_s3 import (
    copy_folders_from_project,
)
from simcore_postgres_database.storage_models import file_meta_data
from simcore_service_storage.simcore_s3_dsm import SimcoreS3DataManager
from sqlalchemy.ext.asyncio import AsyncEngine

pytest_simcore_core_services_selection = ["postgres", "rabbit"]
pytest_simcore_ops_services_selection = ["adminer"]


async def _request_copy_folders(
    rpc_client: RabbitMQRPCClient,
    user_id: UserID,
    product_name: str,
    source_project: dict[str, Any],
    dst_project: dict[str, Any],
    nodes_map: dict[NodeID, NodeID],
) -> dict[str, Any]:
    with log_context(
        logging.INFO,
        f"Copying folders from {source_project['uuid']} to {dst_project['uuid']}",
    ) as ctx:
        async_job_get, async_job_name = await copy_folders_from_project(
            rpc_client,
            user_id=user_id,
            product_name=product_name,
            body=FoldersBody(
                source=source_project, destination=dst_project, nodes_map=nodes_map
            ),
        )

        async for async_job_result in wait_and_get_result(
            rpc_client,
            rpc_namespace=STORAGE_RPC_NAMESPACE,
            method_name=copy_folders_from_project.__name__,
            job_id=async_job_get.job_id,
            job_id_data=async_job_name,
            client_timeout=datetime.timedelta(seconds=60),
        ):
            ctx.logger.info("%s", f"<-- current state is {async_job_result=}")
            if async_job_result.done:
                result = await async_job_result.result()
                assert isinstance(result, AsyncJobResult)
                return result.result

    pytest.fail(reason="Copy folders failed!")


@pytest.mark.xfail(reason="There is something fishy here MB, GC")
async def test_copy_folders_from_non_existing_project(
    initialized_app: FastAPI,
    storage_rabbitmq_rpc_client: RabbitMQRPCClient,
    user_id: UserID,
    product_name: str,
    create_project: Callable[..., Awaitable[dict[str, Any]]],
    faker: Faker,
):
    src_project = await create_project()
    incorrect_src_project = deepcopy(src_project)
    incorrect_src_project["uuid"] = faker.uuid4()
    dst_project = await create_project()
    incorrect_dst_project = deepcopy(dst_project)
    incorrect_dst_project["uuid"] = faker.uuid4()

    with pytest.raises(RuntimeError, match="404") as exc_info:
        await _request_copy_folders(
            storage_rabbitmq_rpc_client,
            user_id,
            product_name,
            incorrect_src_project,
            dst_project,
            nodes_map={},
        )
    # assert_status(
    #     exc_info.value.response,
    #     status.HTTP_404_NOT_FOUND,
    #     None,
    #     expected_msg=f"{incorrect_src_project['uuid']} was not found",
    # )

    with pytest.raises(RuntimeError, match="404") as exc_info:
        await _request_copy_folders(
            storage_rabbitmq_rpc_client,
            user_id,
            product_name,
            src_project,
            incorrect_dst_project,
            nodes_map={},
        )
    # assert_status(
    #     exc_info.value.response,
    #     status.HTTP_404_NOT_FOUND,
    #     None,
    #     expected_msg=f"{incorrect_dst_project['uuid']} was not found",
    # )


async def test_copy_folders_from_empty_project(
    initialized_app: FastAPI,
    storage_rabbitmq_rpc_client: RabbitMQRPCClient,
    user_id: UserID,
    product_name: str,
    create_project: Callable[[], Awaitable[dict[str, Any]]],
    sqlalchemy_async_engine: AsyncEngine,
    storage_s3_client: SimcoreS3API,
):
    # we will copy from src to dst
    src_project = await create_project()
    dst_project = await create_project()

    data = await _request_copy_folders(
        storage_rabbitmq_rpc_client,
        user_id,
        product_name,
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
    product_name: str,
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
        storage_rabbitmq_rpc_client,
        user_id,
        product_name,
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
