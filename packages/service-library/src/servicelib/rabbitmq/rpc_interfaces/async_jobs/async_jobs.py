from typing import Final

from models_library.api_schemas_rpc_async_jobs.async_jobs import (
    AsyncJobAbort,
    AsyncJobAccessData,
    AsyncJobId,
    AsyncJobResult,
    AsyncJobStatus,
)
from models_library.rabbitmq_basic_types import RPCMethodName, RPCNamespace
from pydantic import NonNegativeInt, TypeAdapter

from ... import RabbitMQRPCClient

_DEFAULT_TIMEOUT_S: Final[NonNegativeInt] = 30

_RPC_METHOD_NAME_ADAPTER = TypeAdapter(RPCMethodName)


async def abort(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    *,
    rpc_namespace: RPCNamespace,
    job_id: AsyncJobId,
    access_data: AsyncJobAccessData | None
) -> AsyncJobAbort:
    result = await rabbitmq_rpc_client.request(
        rpc_namespace,
        _RPC_METHOD_NAME_ADAPTER.validate_python("abort"),
        job_id=job_id,
        access_data=access_data,
        timeout_s=_DEFAULT_TIMEOUT_S,
    )
    assert isinstance(result, AsyncJobAbort)
    return result


async def get_status(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    *,
    rpc_namespace: RPCNamespace,
    job_id: AsyncJobId,
    access_data: AsyncJobAccessData | None
) -> AsyncJobStatus:
    result = await rabbitmq_rpc_client.request(
        rpc_namespace,
        _RPC_METHOD_NAME_ADAPTER.validate_python("get_status"),
        job_id=job_id,
        access_data=access_data,
        timeout_s=_DEFAULT_TIMEOUT_S,
    )
    assert isinstance(result, AsyncJobStatus)
    return result


async def get_result(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    *,
    rpc_namespace: RPCNamespace,
    job_id: AsyncJobId,
    access_data: AsyncJobAccessData | None
) -> AsyncJobResult:
    result = await rabbitmq_rpc_client.request(
        rpc_namespace,
        _RPC_METHOD_NAME_ADAPTER.validate_python("get_result"),
        job_id=job_id,
        access_data=access_data,
        timeout_s=_DEFAULT_TIMEOUT_S,
    )
    assert isinstance(result, AsyncJobResult)
    return result
