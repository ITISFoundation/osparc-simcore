from models_library.api_schemas_rpc_async_jobs.async_jobs import (
    AsyncJobFilter,
    AsyncJobGet,
)
from models_library.api_schemas_storage import STORAGE_RPC_NAMESPACE
from models_library.api_schemas_storage.storage_schemas import FoldersBody
from models_library.api_schemas_webserver.storage import PathToExport
from models_library.products import ProductName
from models_library.rabbitmq_basic_types import RPCMethodName
from models_library.users import UserID
from pydantic import TypeAdapter

from ... import RabbitMQRPCClient
from ..async_jobs.async_jobs import submit
from ._utils import get_async_job_filter


async def copy_folders_from_project(
    client: RabbitMQRPCClient,
    *,
    user_id: UserID,
    product_name: ProductName,
    body: FoldersBody,
) -> tuple[AsyncJobGet, AsyncJobFilter]:
    job_filter = get_async_job_filter(user_id=user_id, product_name=product_name)
    async_job_rpc_get = await submit(
        rabbitmq_rpc_client=client,
        rpc_namespace=STORAGE_RPC_NAMESPACE,
        method_name=RPCMethodName("copy_folders_from_project"),
        job_filter=job_filter,
        body=body,
    )
    return async_job_rpc_get, job_filter


async def start_export_data(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    *,
    user_id: UserID,
    product_name: ProductName,
    paths_to_export: list[PathToExport],
) -> tuple[AsyncJobGet, AsyncJobFilter]:
    job_filter = get_async_job_filter(user_id=user_id, product_name=product_name)
    async_job_rpc_get = await submit(
        rabbitmq_rpc_client,
        rpc_namespace=STORAGE_RPC_NAMESPACE,
        method_name=TypeAdapter(RPCMethodName).validate_python("start_export_data"),
        job_filter=job_filter,
        paths_to_export=paths_to_export,
    )
    return async_job_rpc_get, job_filter
