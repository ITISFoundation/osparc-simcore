from typing import Final

from models_library.api_schemas_rpc_long_running_tasks.tasks import (
    TaskRpcGet,
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
from simcore_service_storage.api.rpc._zipping import TaskRpcId

from ... import RabbitMQRPCClient

_DEFAULT_TIMEOUT_S: Final[NonNegativeInt] = 30

_RPC_METHOD_NAME_ADAPTER = TypeAdapter(RPCMethodName)


async def start_zipping(
    rabbitmq_rpc_client: RabbitMQRPCClient, *, paths: ZipTaskStartInput
) -> TaskRpcGet:
    result = await rabbitmq_rpc_client.request(
        STORAGE_RPC_NAMESPACE,
        _RPC_METHOD_NAME_ADAPTER.validate_python("start_zipping"),
        paths=paths,
        timeout_s=_DEFAULT_TIMEOUT_S,
    )
    assert isinstance(result, TaskRpcGet)
    return result


async def abort_zipping(
    rabbitmq_rpc_client: RabbitMQRPCClient, *, task_id: TaskRpcId
) -> ZipTaskAbortOutput:
    result = await rabbitmq_rpc_client.request(
        STORAGE_RPC_NAMESPACE,
        _RPC_METHOD_NAME_ADAPTER.validate_python("abort_zipping"),
        task_id=task_id,
        timeout_s=_DEFAULT_TIMEOUT_S,
    )
    assert isinstance(result, ZipTaskAbortOutput)
    return result


async def get_zipping_status(
    rabbitmq_rpc_client: RabbitMQRPCClient, *, task_id: TaskRpcId
) -> TaskRpcStatus:
    result = await rabbitmq_rpc_client.request(
        STORAGE_RPC_NAMESPACE,
        _RPC_METHOD_NAME_ADAPTER.validate_python("get_zipping_status"),
        task_id=task_id,
        timeout_s=_DEFAULT_TIMEOUT_S,
    )
    assert isinstance(result, TaskRpcStatus)
    return result


async def get_zipping_result(
    rabbitmq_rpc_client: RabbitMQRPCClient, *, task_id: TaskRpcId
) -> TaskRpcResult:
    result = await rabbitmq_rpc_client.request(
        STORAGE_RPC_NAMESPACE,
        _RPC_METHOD_NAME_ADAPTER.validate_python("get_zipping_result"),
        task_id=task_id,
        timeout_s=_DEFAULT_TIMEOUT_S,
    )
    assert isinstance(result, TaskRpcResult)
    return result
