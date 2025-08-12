import logging
from datetime import timedelta
from typing import Any, Final

from models_library.rabbitmq_basic_types import RPCMethodName
from pydantic import PositiveInt, TypeAdapter

from ...logging_utils import log_decorator
from ...long_running_tasks.task import RegisteredTaskName
from ...rabbitmq._client_rpc import RabbitMQRPCClient
from .._serialization import string_to_object
from ..models import RabbitNamespace, TaskBase, TaskContext, TaskId, TaskStatus
from .namespace import get_namespace

_logger = logging.getLogger(__name__)

_RPC_TIMEOUT_VERY_LONG_REQUEST: Final[PositiveInt] = int(
    timedelta(minutes=60).total_seconds()
)
_RPC_TIMEOUT_NORMAL_REQUEST: Final[PositiveInt] = int(
    timedelta(seconds=30).total_seconds()
)


@log_decorator(_logger, level=logging.DEBUG)
async def start_task(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    namespace: RabbitNamespace,
    *,
    registered_task_name: RegisteredTaskName,
    unique: bool = False,
    task_context: TaskContext | None = None,
    task_name: str | None = None,
    fire_and_forget: bool = False,
    **task_kwargs: Any,
) -> TaskId:
    result = await rabbitmq_rpc_client.request(
        get_namespace(namespace),
        TypeAdapter(RPCMethodName).validate_python("start_task"),
        registered_task_name=registered_task_name,
        unique=unique,
        task_context=task_context,
        task_name=task_name,
        fire_and_forget=fire_and_forget,
        **task_kwargs,
        timeout_s=_RPC_TIMEOUT_NORMAL_REQUEST,
    )
    assert isinstance(result, TaskId)  # nosec
    return result


@log_decorator(_logger, level=logging.DEBUG)
async def list_tasks(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    namespace: RabbitNamespace,
    *,
    task_context: TaskContext,
) -> list[TaskBase]:
    result = await rabbitmq_rpc_client.request(
        get_namespace(namespace),
        TypeAdapter(RPCMethodName).validate_python("list_tasks"),
        task_context=task_context,
        timeout_s=_RPC_TIMEOUT_NORMAL_REQUEST,
    )
    return TypeAdapter(list[TaskBase]).validate_python(result)


@log_decorator(_logger, level=logging.DEBUG)
async def get_task_status(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    namespace: RabbitNamespace,
    *,
    task_context: TaskContext,
    task_id: TaskId,
) -> TaskStatus:
    result = await rabbitmq_rpc_client.request(
        get_namespace(namespace),
        TypeAdapter(RPCMethodName).validate_python("get_task_status"),
        task_context=task_context,
        task_id=task_id,
        timeout_s=_RPC_TIMEOUT_NORMAL_REQUEST,
    )
    assert isinstance(result, TaskStatus)  # nosec
    return result


@log_decorator(_logger, level=logging.DEBUG)
async def get_task_result(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    namespace: RabbitNamespace,
    *,
    task_context: TaskContext,
    task_id: TaskId,
) -> Any:
    serialized_result = await rabbitmq_rpc_client.request(
        get_namespace(namespace),
        TypeAdapter(RPCMethodName).validate_python("get_task_result"),
        task_context=task_context,
        task_id=task_id,
        timeout_s=_RPC_TIMEOUT_NORMAL_REQUEST,
    )
    assert isinstance(serialized_result, str)  # nosec
    task_result = string_to_object(serialized_result)

    if isinstance(task_result, Exception):
        raise task_result
    return task_result


@log_decorator(_logger, level=logging.DEBUG)
async def remove_task(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    namespace: RabbitNamespace,
    *,
    task_context: TaskContext,
    task_id: TaskId,
    reraise_errors: bool = True,
) -> None:
    result = await rabbitmq_rpc_client.request(
        get_namespace(namespace),
        TypeAdapter(RPCMethodName).validate_python("remove_task"),
        task_context=task_context,
        task_id=task_id,
        reraise_errors=reraise_errors,
        timeout_s=_RPC_TIMEOUT_VERY_LONG_REQUEST,
    )
    assert result is None  # nosec
