import logging
from datetime import timedelta
from typing import Any, Final

from models_library.rabbitmq_basic_types import RPCMethodName
from pydantic import PositiveInt, TypeAdapter

from ..logging_utils import log_decorator
from ..rabbitmq._client_rpc import RabbitMQRPCClient
from ._rabbit_namespace import get_rabbit_namespace
from ._serialization import loads
from .errors import RPCTransferrableTaskError
from .models import (
    LRTNamespace,
    RegisteredTaskName,
    TaskBase,
    TaskContext,
    TaskId,
    TaskStatus,
)

_logger = logging.getLogger(__name__)

_RPC_TIMEOUT_SHORT_REQUESTS: Final[PositiveInt] = int(
    timedelta(seconds=20).total_seconds()
)


@log_decorator(_logger, level=logging.DEBUG)
async def start_task(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    namespace: LRTNamespace,
    *,
    registered_task_name: RegisteredTaskName,
    unique: bool = False,
    task_context: TaskContext | None = None,
    task_name: str | None = None,
    fire_and_forget: bool = False,
    **task_kwargs: Any,
) -> TaskId:
    result = await rabbitmq_rpc_client.request(
        get_rabbit_namespace(namespace),
        TypeAdapter(RPCMethodName).validate_python("start_task"),
        registered_task_name=registered_task_name,
        unique=unique,
        task_context=task_context,
        task_name=task_name,
        fire_and_forget=fire_and_forget,
        **task_kwargs,
        timeout_s=_RPC_TIMEOUT_SHORT_REQUESTS,
    )
    assert isinstance(result, TaskId)  # nosec
    return result


@log_decorator(_logger, level=logging.DEBUG)
async def list_tasks(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    namespace: LRTNamespace,
    *,
    task_context: TaskContext,
) -> list[TaskBase]:
    result = await rabbitmq_rpc_client.request(
        get_rabbit_namespace(namespace),
        TypeAdapter(RPCMethodName).validate_python("list_tasks"),
        task_context=task_context,
        timeout_s=_RPC_TIMEOUT_SHORT_REQUESTS,
    )
    return TypeAdapter(list[TaskBase]).validate_python(result)


@log_decorator(_logger, level=logging.DEBUG)
async def get_task_status(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    namespace: LRTNamespace,
    *,
    task_context: TaskContext,
    task_id: TaskId,
) -> TaskStatus:
    result = await rabbitmq_rpc_client.request(
        get_rabbit_namespace(namespace),
        TypeAdapter(RPCMethodName).validate_python("get_task_status"),
        task_context=task_context,
        task_id=task_id,
        timeout_s=_RPC_TIMEOUT_SHORT_REQUESTS,
    )
    assert isinstance(result, TaskStatus)  # nosec
    return result


@log_decorator(_logger, level=logging.DEBUG)
async def get_task_result(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    namespace: LRTNamespace,
    *,
    task_context: TaskContext,
    task_id: TaskId,
) -> Any:
    try:
        serialized_result = await rabbitmq_rpc_client.request(
            get_rabbit_namespace(namespace),
            TypeAdapter(RPCMethodName).validate_python("get_task_result"),
            task_context=task_context,
            task_id=task_id,
            timeout_s=_RPC_TIMEOUT_SHORT_REQUESTS,
        )
        assert isinstance(serialized_result, str)  # nosec
        return loads(serialized_result)
    except RPCTransferrableTaskError as e:
        decoded_error = loads(f"{e}")
        raise decoded_error from e


@log_decorator(_logger, level=logging.DEBUG)
async def remove_task(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    namespace: LRTNamespace,
    *,
    task_context: TaskContext,
    task_id: TaskId,
) -> None:

    result = await rabbitmq_rpc_client.request(
        get_rabbit_namespace(namespace),
        TypeAdapter(RPCMethodName).validate_python("remove_task"),
        task_context=task_context,
        task_id=task_id,
        timeout_s=_RPC_TIMEOUT_SHORT_REQUESTS,
    )
    assert result is None  # nosec
