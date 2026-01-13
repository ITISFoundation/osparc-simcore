from typing import Annotated

from fastapi import Depends
from servicelib.rabbitmq._client_rpc import RabbitMQRPCClient

from ...services_rpc.async_jobs import AsyncJobClient
from .celery import get_task_manager


def get_async_jobs_client(
    task_manager: Annotated[RabbitMQRPCClient, Depends(get_task_manager)],
) -> AsyncJobClient:
    return AsyncJobClient(_rabbitmq_rpc_client=task_manager)
