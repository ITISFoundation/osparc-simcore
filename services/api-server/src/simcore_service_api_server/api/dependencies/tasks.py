from typing import Annotated

from fastapi import Depends
from servicelib.rabbitmq._client_rpc import RabbitMQRPCClient

from ...services_rpc.async_jobs import AsyncJobClient
from .rabbitmq import get_rabbitmq_rpc_client


def get_async_jobs_client(
    rabbitmq_rpc_client: Annotated[RabbitMQRPCClient, Depends(get_rabbitmq_rpc_client)],
) -> AsyncJobClient:
    return AsyncJobClient(_rabbitmq_rpc_client=rabbitmq_rpc_client)
