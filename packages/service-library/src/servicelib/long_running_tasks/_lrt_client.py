import logging
from datetime import timedelta
from typing import Any, Final

from models_library.rabbitmq_basic_types import RPCMethodName
from pydantic import PositiveInt, TypeAdapter

from ..logging_errors import create_troubleshootting_log_kwargs
from ..logging_utils import log_decorator
from ..rabbitmq._client_rpc import RabbitMQRPCClient
from ._rabbit_namespace import get_rabbit_namespace
from ._serialization import object_to_string, string_to_object
from .models import (
    ErrorResponse,
    LRTNamespace,
    TaskBase,
    TaskContext,
    TaskId,
    TaskStatus,
)
from .task import RegisteredTaskName

_logger = logging.getLogger(__name__)

_RPC_MAX_CANCELLATION_TIMEOUT: Final[PositiveInt] = int(
    timedelta(minutes=60).total_seconds()
)
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
    allowed_errors: tuple[type[BaseException], ...],
) -> Any:
    serialized_result = await rabbitmq_rpc_client.request(
        get_rabbit_namespace(namespace),
        TypeAdapter(RPCMethodName).validate_python("get_task_result"),
        task_context=task_context,
        task_id=task_id,
        allowed_errors_str=object_to_string(allowed_errors),
        timeout_s=_RPC_TIMEOUT_SHORT_REQUESTS,
    )
    assert isinstance(serialized_result, ErrorResponse | str)  # nosec
    if isinstance(serialized_result, ErrorResponse):
        error = string_to_object(serialized_result.str_error_object)
        _logger.info(
            **create_troubleshootting_log_kwargs(
                f"Task '{task_id}' raised the following error:\n{serialized_result.str_traceback}",
                error=error,
                error_context={
                    "task_id": task_id,
                    "namespace": namespace,
                    "task_context": task_context,
                    "allowed_errors": allowed_errors,
                },
                tip=(
                    f"The caller of this function should handle the exception. "
                    f"To figure out where it was running check {namespace=}"
                ),
            )
        )
        raise error

    return string_to_object(serialized_result)


@log_decorator(_logger, level=logging.DEBUG)
async def remove_task(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    namespace: LRTNamespace,
    *,
    task_context: TaskContext,
    task_id: TaskId,
    wait_for_removal: bool,
    reraise_errors: bool,
    cancellation_timeout: timedelta | None = None,
) -> None:
    timeout_s = (
        _RPC_MAX_CANCELLATION_TIMEOUT
        if cancellation_timeout is None
        else int(cancellation_timeout.total_seconds())
    )

    # NOTE: task always gets cancelled even if not waiting for it
    # request will return immediatlye, no need to wait so much
    if not wait_for_removal:
        timeout_s = _RPC_TIMEOUT_SHORT_REQUESTS

    result = await rabbitmq_rpc_client.request(
        get_rabbit_namespace(namespace),
        TypeAdapter(RPCMethodName).validate_python("remove_task"),
        task_context=task_context,
        task_id=task_id,
        wait_for_removal=wait_for_removal,
        reraise_errors=reraise_errors,
        timeout_s=timeout_s,
    )
    assert result is None  # nosec
