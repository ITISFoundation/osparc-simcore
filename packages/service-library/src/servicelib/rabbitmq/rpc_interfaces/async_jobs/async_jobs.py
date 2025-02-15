from typing import Final

from models_library.api_schemas_rpc_data_export.async_jobs import (
    AsyncJobRpcId,
    AsyncJobRpcResult,
    AsyncJobRpcStatus,
)
from models_library.api_schemas_storage.data_export_tasks import (
    DataExportTaskAbortOutput,
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
    task_id: AsyncJobRpcId
) -> DataExportTaskAbortOutput:
    result = await rabbitmq_rpc_client.request(
        rpc_namespace,
        _RPC_METHOD_NAME_ADAPTER.validate_python("abort"),
        task_id=task_id,
        timeout_s=_DEFAULT_TIMEOUT_S,
    )
    assert isinstance(result, DataExportTaskAbortOutput)
    return result


async def get_status(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    *,
    rpc_namespace: RPCNamespace,
    task_id: AsyncJobRpcId
) -> AsyncJobRpcStatus:
    result = await rabbitmq_rpc_client.request(
        rpc_namespace,
        _RPC_METHOD_NAME_ADAPTER.validate_python("get_status"),
        task_id=task_id,
        timeout_s=_DEFAULT_TIMEOUT_S,
    )
    assert isinstance(result, AsyncJobRpcStatus)
    return result


async def get_result(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    *,
    rpc_namespace: RPCNamespace,
    task_id: AsyncJobRpcId
) -> AsyncJobRpcResult:
    result = await rabbitmq_rpc_client.request(
        rpc_namespace,
        _RPC_METHOD_NAME_ADAPTER.validate_python("get_result"),
        task_id=task_id,
        timeout_s=_DEFAULT_TIMEOUT_S,
    )
    assert isinstance(result, AsyncJobRpcResult)
    return result
