import datetime
from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import PlainTextResponse
from models_library.errors import RABBITMQ_CLIENT_UNHEALTHY_MSG, REDIS_CLIENT_UNHEALTHY_MSG
from servicelib.fastapi.health import HealthCheckError
from servicelib.rabbitmq import RabbitMQClient, RabbitMQRPCClient
from servicelib.redis import RedisClientsManager

from ...api.dependencies.rabbitmq import (
    get_rabbitmq_client_from_request,
    get_redis_client_manager_from_request,
    rabbitmq_rpc_client,
)

router = APIRouter()


@router.get("/", response_class=PlainTextResponse)
async def check_service_health(
    rabbitmq_client: Annotated[RabbitMQClient, Depends(get_rabbitmq_client_from_request)],
    rabbitmq_rpc: Annotated[RabbitMQRPCClient, Depends(rabbitmq_rpc_client)],
    redis_clients_manager: Annotated[RedisClientsManager, Depends(get_redis_client_manager_from_request)],
):
    if not rabbitmq_client.healthy or not rabbitmq_rpc.healthy:
        raise HealthCheckError(RABBITMQ_CLIENT_UNHEALTHY_MSG)

    if not redis_clients_manager.healthy:
        raise HealthCheckError(REDIS_CLIENT_UNHEALTHY_MSG)

    return f"{__name__}@{datetime.datetime.now(tz=datetime.UTC).isoformat()}"
