from typing import Final

from models_library.api_schemas_rpc_data_export.tasks import (
    TaskRpcId,
    TaskRpcResult,
    TaskRpcStatus,
)
from models_library.api_schemas_storage import STORAGE_RPC_NAMESPACE
from models_library.api_schemas_storage.data_export_tasks import (
    DataExportTaskAbortOutput,
)
from models_library.rabbitmq_basic_types import RPCMethodName
from pydantic import NonNegativeInt, TypeAdapter

from ... import RabbitMQRPCClient

_DEFAULT_TIMEOUT_S: Final[NonNegativeInt] = 30

_RPC_METHOD_NAME_ADAPTER = TypeAdapter(RPCMethodName)


async def abort(
    rabbitmq_rpc_client: RabbitMQRPCClient, *, task_id: TaskRpcId
) -> DataExportTaskAbortOutput:
    result = await rabbitmq_rpc_client.request(
        STORAGE_RPC_NAMESPACE,
        _RPC_METHOD_NAME_ADAPTER.validate_python("abort_data_export"),
        task_id=task_id,
        timeout_s=_DEFAULT_TIMEOUT_S,
    )
    assert isinstance(result, DataExportTaskAbortOutput)
    return result


async def get_status(
    rabbitmq_rpc_client: RabbitMQRPCClient, *, task_id: TaskRpcId
) -> TaskRpcStatus:
    result = await rabbitmq_rpc_client.request(
        STORAGE_RPC_NAMESPACE,
        _RPC_METHOD_NAME_ADAPTER.validate_python("get_data_export_status"),
        task_id=task_id,
        timeout_s=_DEFAULT_TIMEOUT_S,
    )
    assert isinstance(result, TaskRpcStatus)
    return result


async def get_result(
    rabbitmq_rpc_client: RabbitMQRPCClient, *, task_id: TaskRpcId
) -> TaskRpcResult:
    result = await rabbitmq_rpc_client.request(
        STORAGE_RPC_NAMESPACE,
        _RPC_METHOD_NAME_ADAPTER.validate_python("get_data_export_result"),
        task_id=task_id,
        timeout_s=_DEFAULT_TIMEOUT_S,
    )
    assert isinstance(result, TaskRpcResult)
    return result
