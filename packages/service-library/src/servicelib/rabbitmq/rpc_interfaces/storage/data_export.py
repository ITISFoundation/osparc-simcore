from typing import Final

from models_library.api_schemas_rpc_long_running_tasks.tasks import (
    TaskRpcGet,
    TaskRpcId,
    TaskRpcResult,
    TaskRpcStatus,
)
from models_library.api_schemas_storage import STORAGE_RPC_NAMESPACE
from models_library.api_schemas_storage.zipping_tasks import (
    ZipTaskAbortOutput,
    ZipTaskStartInput,
)
from models_library.rabbitmq_basic_types import RPCMethodName
from pydantic import NonNegativeInt, TypeAdapter

from ... import RabbitMQRPCClient

_DEFAULT_TIMEOUT_S: Final[NonNegativeInt] = 30

_RPC_METHOD_NAME_ADAPTER = TypeAdapter(RPCMethodName)


async def start_data_export(
    rabbitmq_rpc_client: RabbitMQRPCClient, *, paths: ZipTaskStartInput
) -> TaskRpcGet:
    result = await rabbitmq_rpc_client.request(
        STORAGE_RPC_NAMESPACE,
        _RPC_METHOD_NAME_ADAPTER.validate_python("start_data_export"),
        paths=paths,
        timeout_s=_DEFAULT_TIMEOUT_S,
    )
    assert isinstance(result, TaskRpcGet)
    return result


async def abort_data_export(
    rabbitmq_rpc_client: RabbitMQRPCClient, *, task_id: TaskRpcId
) -> ZipTaskAbortOutput:
    result = await rabbitmq_rpc_client.request(
        STORAGE_RPC_NAMESPACE,
        _RPC_METHOD_NAME_ADAPTER.validate_python("abort_data_export"),
        task_id=task_id,
        timeout_s=_DEFAULT_TIMEOUT_S,
    )
    assert isinstance(result, ZipTaskAbortOutput)
    return result


async def get_data_export_status(
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


async def get_data_export_result(
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
