import datetime
import logging
from collections.abc import Awaitable, Callable
from copy import deepcopy
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
from models_library.projects_nodes_io import NodeID
from models_library.users import UserID
from pytest_simcore.helpers.logging_tools import log_context
from servicelib.rabbitmq._client_rpc import RabbitMQRPCClient
from servicelib.rabbitmq.rpc_interfaces.async_jobs.async_jobs import wait_and_get_result
from servicelib.rabbitmq.rpc_interfaces.storage.simcore_s3 import (
    copy_folders_from_project,
)
from simcore_postgres_database.storage_models import file_meta_data
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
