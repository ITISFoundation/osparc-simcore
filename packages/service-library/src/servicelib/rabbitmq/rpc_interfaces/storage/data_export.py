from models_library.api_schemas_rpc_async_jobs.async_jobs import (
    AsyncJobGet,
    AsyncJobNameData,
)
from models_library.api_schemas_storage import STORAGE_RPC_NAMESPACE
from models_library.rabbitmq_basic_types import RPCMethodName
from pydantic import TypeAdapter

from ... import RabbitMQRPCClient
from ..async_jobs.async_jobs import submit


async def start_data_export(
    rabbitmq_rpc_client: RabbitMQRPCClient, *, job_id_data: AsyncJobNameData, **kwargs
) -> AsyncJobGet:
    return await submit(
        rabbitmq_rpc_client,
        rpc_namespace=STORAGE_RPC_NAMESPACE,
        method_name=TypeAdapter(RPCMethodName).validate_python("start_data_export"),
        job_id_data=job_id_data,
        **kwargs,
    )
