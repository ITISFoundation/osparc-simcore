from typing import Final

from models_library.api_schemas_rpc_async_jobs.async_jobs import (
    AsyncJobAbort,
    AsyncJobGet,
    AsyncJobId,
    AsyncJobNameData,
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
    job_id_data: AsyncJobNameData
) -> AsyncJobAbort:
    result = await rabbitmq_rpc_client.request(
        rpc_namespace,
        _RPC_METHOD_NAME_ADAPTER.validate_python("abort"),
        job_id=job_id,
        job_id_data=job_id_data,
        timeout_s=_DEFAULT_TIMEOUT_S,
    )
    assert isinstance(result, AsyncJobAbort)
    return result


async def get_status(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    *,
    rpc_namespace: RPCNamespace,
    job_id: AsyncJobId,
    job_id_data: AsyncJobNameData
) -> AsyncJobStatus:
    result = await rabbitmq_rpc_client.request(
        rpc_namespace,
        _RPC_METHOD_NAME_ADAPTER.validate_python("get_status"),
        job_id=job_id,
        job_id_data=job_id_data,
        timeout_s=_DEFAULT_TIMEOUT_S,
    )
    assert isinstance(result, AsyncJobStatus)
    return result


async def get_result(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    *,
    rpc_namespace: RPCNamespace,
    job_id: AsyncJobId,
    job_id_data: AsyncJobNameData
) -> AsyncJobResult:
    result = await rabbitmq_rpc_client.request(
        rpc_namespace,
        _RPC_METHOD_NAME_ADAPTER.validate_python("get_result"),
        job_id=job_id,
        job_id_data=job_id_data,
        timeout_s=_DEFAULT_TIMEOUT_S,
    )
    assert isinstance(result, AsyncJobResult)
    return result


async def list_jobs(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    *,
    rpc_namespace: RPCNamespace,
    filter_: str,
    job_id_data: AsyncJobNameData
) -> list[AsyncJobGet]:
    result: list[AsyncJobGet] = await rabbitmq_rpc_client.request(
        rpc_namespace,
        _RPC_METHOD_NAME_ADAPTER.validate_python("list_jobs"),
        filter_=filter_,
        job_id_data=job_id_data,
        timeout_s=_DEFAULT_TIMEOUT_S,
    )
    return result


async def submit_job(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    *,
    rpc_namespace: RPCNamespace,
    method_name: str,
    job_id_data: AsyncJobNameData,
    **kwargs
) -> AsyncJobGet:
    result = await rabbitmq_rpc_client.request(
        rpc_namespace,
        _RPC_METHOD_NAME_ADAPTER.validate_python(method_name),
        job_id_data=job_id_data,
        **kwargs,
        timeout_s=_DEFAULT_TIMEOUT_S,
    )
    assert isinstance(result, AsyncJobGet)
    return result
