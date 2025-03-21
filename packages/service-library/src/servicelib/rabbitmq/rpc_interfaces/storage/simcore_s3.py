from models_library.api_schemas_rpc_async_jobs.async_jobs import (
    AsyncJobGet,
    AsyncJobNameData,
)
from models_library.api_schemas_storage import STORAGE_RPC_NAMESPACE
from models_library.api_schemas_storage.storage_schemas import FoldersBody
from models_library.rabbitmq_basic_types import RPCMethodName
from models_library.users import UserID

from ..._client_rpc import RabbitMQRPCClient
from ..async_jobs.async_jobs import submit


async def copy_folders_from_project(
    client: RabbitMQRPCClient,
    *,
    user_id: UserID,
    product_name: str,
    body: FoldersBody,
) -> tuple[AsyncJobGet, AsyncJobNameData]:
    job_id_data = AsyncJobNameData(user_id=user_id, product_name=product_name)
    async_job_rpc_get = await submit(
        rabbitmq_rpc_client=client,
        rpc_namespace=STORAGE_RPC_NAMESPACE,
        method_name=RPCMethodName("copy_folders_from_project"),
        job_id_data=job_id_data,
        body=body,
    )
    return async_job_rpc_get, job_id_data
