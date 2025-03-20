from typing import Final

from models_library.api_schemas_rpc_async_jobs.async_jobs import (
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


async def cancel(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    *,
    rpc_namespace: RPCNamespace,
    job_id: AsyncJobId,
    job_id_data: AsyncJobNameData,
) -> None:
    await rabbitmq_rpc_client.request(
        rpc_namespace,
        _RPC_METHOD_NAME_ADAPTER.validate_python("cancel"),
        job_id=job_id,
        job_id_data=job_id_data,
        timeout_s=_DEFAULT_TIMEOUT_S,
    )


async def status(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    *,
    rpc_namespace: RPCNamespace,
    job_id: AsyncJobId,
    job_id_data: AsyncJobNameData,
) -> AsyncJobStatus:
    _result = await rabbitmq_rpc_client.request(
        rpc_namespace,
        _RPC_METHOD_NAME_ADAPTER.validate_python("status"),
        job_id=job_id,
        job_id_data=job_id_data,
        timeout_s=_DEFAULT_TIMEOUT_S,
    )
    assert isinstance(_result, AsyncJobStatus)
    return _result


async def result(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    *,
    rpc_namespace: RPCNamespace,
    job_id: AsyncJobId,
    job_id_data: AsyncJobNameData,
) -> AsyncJobResult:
    _result = await rabbitmq_rpc_client.request(
        rpc_namespace,
        _RPC_METHOD_NAME_ADAPTER.validate_python("result"),
        job_id=job_id,
        job_id_data=job_id_data,
        timeout_s=_DEFAULT_TIMEOUT_S,
    )
    assert isinstance(_result, AsyncJobResult)
    return _result


async def list_jobs(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    *,
    rpc_namespace: RPCNamespace,
    filter_: str,
    job_id_data: AsyncJobNameData,
) -> list[AsyncJobGet]:
    _result: list[AsyncJobGet] = await rabbitmq_rpc_client.request(
        rpc_namespace,
        _RPC_METHOD_NAME_ADAPTER.validate_python("list_jobs"),
        filter_=filter_,
        job_id_data=job_id_data,
        timeout_s=_DEFAULT_TIMEOUT_S,
    )
    return _result


async def submit(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    *,
    rpc_namespace: RPCNamespace,
    method_name: str,
    job_id_data: AsyncJobNameData,
    **kwargs,
) -> AsyncJobGet:
    _result = await rabbitmq_rpc_client.request(
        rpc_namespace,
        _RPC_METHOD_NAME_ADAPTER.validate_python(method_name),
        job_id_data=job_id_data,
        **kwargs,
        timeout_s=_DEFAULT_TIMEOUT_S,
    )
    assert isinstance(_result, AsyncJobGet)  # nosec
    return _result
