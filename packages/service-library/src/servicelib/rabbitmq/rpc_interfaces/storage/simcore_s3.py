from typing import Literal

from models_library.api_schemas_rpc_async_jobs.async_jobs import (
    AsyncJobGet,
    AsyncJobOwnerMetadata,
)
from models_library.api_schemas_storage import STORAGE_RPC_NAMESPACE
from models_library.api_schemas_storage.storage_schemas import FoldersBody
from models_library.api_schemas_webserver.storage import PathToExport
from models_library.rabbitmq_basic_types import RPCMethodName
from pydantic import TypeAdapter

from ... import RabbitMQRPCClient
from ..async_jobs.async_jobs import submit


async def copy_folders_from_project(
    client: RabbitMQRPCClient, *, body: FoldersBody, job_filter: AsyncJobOwnerMetadata
) -> tuple[AsyncJobGet, AsyncJobOwnerMetadata]:
    async_job_rpc_get = await submit(
        rabbitmq_rpc_client=client,
        rpc_namespace=STORAGE_RPC_NAMESPACE,
        method_name=TypeAdapter(RPCMethodName).validate_python(
            "copy_folders_from_project"
        ),
        job_filter=job_filter,
        body=body,
    )
    return async_job_rpc_get, job_filter


async def start_export_data(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    *,
    paths_to_export: list[PathToExport],
    export_as: Literal["path", "download_link"],
    job_filter: AsyncJobOwnerMetadata
) -> tuple[AsyncJobGet, AsyncJobOwnerMetadata]:
    async_job_rpc_get = await submit(
        rabbitmq_rpc_client,
        rpc_namespace=STORAGE_RPC_NAMESPACE,
        method_name=TypeAdapter(RPCMethodName).validate_python("start_export_data"),
        job_filter=job_filter,
        paths_to_export=paths_to_export,
        export_as=export_as,
    )
    return async_job_rpc_get, job_filter
