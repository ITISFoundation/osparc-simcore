from typing import Literal

from models_library.api_schemas_rpc_async_jobs.async_jobs import (
    AsyncJobGet,
)
from models_library.api_schemas_storage import STORAGE_RPC_NAMESPACE
from models_library.api_schemas_storage.storage_schemas import FoldersBody
from models_library.api_schemas_webserver.storage import PathToExport
from models_library.rabbitmq_basic_types import RPCMethodName
from models_library.users import UserID
from pydantic import TypeAdapter
from servicelib.celery.models import OwnerMetadata

from ... import RabbitMQRPCClient
from ..async_jobs.async_jobs import submit


async def copy_folders_from_project(
    client: RabbitMQRPCClient,
    *,
    body: FoldersBody,
    owner_metadata: OwnerMetadata,
    user_id: UserID,
) -> tuple[AsyncJobGet, OwnerMetadata]:
    async_job_rpc_get = await submit(
        rabbitmq_rpc_client=client,
        rpc_namespace=STORAGE_RPC_NAMESPACE,
        method_name=TypeAdapter(RPCMethodName).validate_python(
            "copy_folders_from_project"
        ),
        owner_metadata=owner_metadata,
        body=body,
        user_id=user_id,
    )
    return async_job_rpc_get, owner_metadata


async def start_export_data(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    *,
    paths_to_export: list[PathToExport],
    export_as: Literal["path", "download_link"],
    owner_metadata: OwnerMetadata,
    user_id: UserID,
) -> tuple[AsyncJobGet, OwnerMetadata]:
    async_job_rpc_get = await submit(
        rabbitmq_rpc_client,
        rpc_namespace=STORAGE_RPC_NAMESPACE,
        method_name=TypeAdapter(RPCMethodName).validate_python("start_export_data"),
        owner_metadata=owner_metadata,
        paths_to_export=paths_to_export,
        export_as=export_as,
        user_id=user_id,
    )
    return async_job_rpc_get, owner_metadata
