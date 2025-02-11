from typing import Final

from models_library.api_schemas_long_running_tasks.base import TaskId
from models_library.api_schemas_long_running_tasks.tasks import (
    TaskGet,
    TaskResult,
    TaskStatus,
)
from models_library.rabbitmq_basic_types import RPCMethodName
from models_library.storage_schemas import STORAGE_RPC_NAMESPACE
from models_library.storage_schemas.zipping_tasks import (
    ZipTaskAbortOutput,
    ZipTaskStartInput,
)
from pydantic import NonNegativeInt, TypeAdapter

from ... import RabbitMQRPCClient

_DEFAULT_TIMEOUT_S: Final[NonNegativeInt] = 30

_RPC_METHOD_NAME_ADAPTER = TypeAdapter(RPCMethodName)


async def start_zipping(
    rabbitmq_rpc_client: RabbitMQRPCClient, *, paths: ZipTaskStartInput
) -> TaskGet:
    result = await rabbitmq_rpc_client.request(
        STORAGE_RPC_NAMESPACE,
        _RPC_METHOD_NAME_ADAPTER.validate_python("start_zipping"),
        paths=paths,
        timeout_s=_DEFAULT_TIMEOUT_S,
    )
    assert isinstance(result, TaskGet)
    return result


async def abort_zipping(
    rabbitmq_rpc_client: RabbitMQRPCClient, *, task_id: TaskId
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
    rabbitmq_rpc_client: RabbitMQRPCClient, *, task_id: TaskId
) -> TaskStatus:
    result = await rabbitmq_rpc_client.request(
        STORAGE_RPC_NAMESPACE,
        _RPC_METHOD_NAME_ADAPTER.validate_python("get_zipping_status"),
        task_id=task_id,
        timeout_s=_DEFAULT_TIMEOUT_S,
    )
    assert isinstance(result, TaskStatus)
    return result


async def get_zipping_result(
    rabbitmq_rpc_client: RabbitMQRPCClient, *, task_id: TaskId
) -> TaskResult:
    result = await rabbitmq_rpc_client.request(
        STORAGE_RPC_NAMESPACE,
        _RPC_METHOD_NAME_ADAPTER.validate_python("get_zipping_result"),
        task_id=task_id,
        timeout_s=_DEFAULT_TIMEOUT_S,
    )
    assert isinstance(result, TaskResult)
    return result
