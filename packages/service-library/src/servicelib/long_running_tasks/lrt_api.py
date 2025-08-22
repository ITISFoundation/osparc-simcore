from datetime import timedelta
from typing import Any

from ..rabbitmq._client_rpc import RabbitMQRPCClient
from . import _rpc_client
from .models import (
    LRTNamespace,
    RegisteredTaskName,
    TaskBase,
    TaskContext,
    TaskId,
    TaskStatus,
)


async def start_task(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    lrt_namespace: LRTNamespace,
    registered_task_name: RegisteredTaskName,
    *,
    unique: bool = False,
    task_context: TaskContext | None = None,
    task_name: str | None = None,
    fire_and_forget: bool = False,
    **task_kwargs: Any,
) -> TaskId:
    """
    Creates a background task from an async function.

    An asyncio task will be created out of it by injecting a `TaskProgress` as the first
    positional argument and adding all `handler_kwargs` as named parameters.

    NOTE: the progress is automatically bounded between 0 and 1
    NOTE: the `task` name must be unique in the module, otherwise when using
        the unique parameter is True, it will not be able to distinguish between
        them.

    Args:
        tasks_manager (TasksManager): the tasks manager
        task (TaskProtocol): the tasks to be run in the background
        unique (bool, optional): If True, then only one such named task may be run. Defaults to False.
        task_context (Optional[TaskContext], optional): a task context storage can be retrieved during the task lifetime. Defaults to None.
        task_name (Optional[str], optional): optional task name. Defaults to None.
        fire_and_forget: if True, then the task will not be cancelled if the status is never called

    Raises:
        TaskAlreadyRunningError: if unique is True, will raise if more than 1 such named task is started

    Returns:
        TaskId: the task unique identifier
    """

    return await _rpc_client.start_task(
        rabbitmq_rpc_client,
        lrt_namespace,
        registered_task_name=registered_task_name,
        unique=unique,
        task_context=task_context,
        task_name=task_name,
        fire_and_forget=fire_and_forget,
        **task_kwargs,
    )


async def list_tasks(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    lrt_namespace: LRTNamespace,
    task_context: TaskContext,
) -> list[TaskBase]:
    return await _rpc_client.list_tasks(
        rabbitmq_rpc_client, lrt_namespace, task_context=task_context
    )


async def get_task_status(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    lrt_namespace: LRTNamespace,
    task_context: TaskContext,
    task_id: TaskId,
) -> TaskStatus:
    """returns the status of a task"""
    return await _rpc_client.get_task_status(
        rabbitmq_rpc_client, lrt_namespace, task_id=task_id, task_context=task_context
    )


async def get_task_result(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    lrt_namespace: LRTNamespace,
    task_context: TaskContext,
    task_id: TaskId,
) -> Any:
    return await _rpc_client.get_task_result(
        rabbitmq_rpc_client,
        lrt_namespace,
        task_context=task_context,
        task_id=task_id,
    )


async def remove_task(
    rabbitmq_rpc_client: RabbitMQRPCClient,
    lrt_namespace: LRTNamespace,
    task_context: TaskContext,
    task_id: TaskId,
    *,
    wait_for_removal: bool,
    cancellation_timeout: timedelta | None = None,
) -> None:
    """cancels and removes a task

    When `wait_for_removal` is True, `cancellationt_timeout` is set to _RPC_TIMEOUT_SHORT_REQUESTS
    """
    await _rpc_client.remove_task(
        rabbitmq_rpc_client,
        lrt_namespace,
        task_id=task_id,
        task_context=task_context,
        wait_for_removal=wait_for_removal,
        cancellation_timeout=cancellation_timeout,
    )
