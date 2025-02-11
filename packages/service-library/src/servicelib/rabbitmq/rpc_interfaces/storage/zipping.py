from typing import Final

from models_library.api_schemas_long_running_tasks.base import TaskId
from models_library.api_schemas_long_running_tasks.tasks import TaskGet
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
