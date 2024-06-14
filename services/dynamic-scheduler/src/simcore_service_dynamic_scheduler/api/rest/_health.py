from typing import Annotated

import arrow
from fastapi import APIRouter, Depends
from fastapi.responses import PlainTextResponse
from models_library.errors import (
    RABBITMQ_CLIENT_UNHEALTHY_MSG,
    REDIS_CLIENT_UNHEALTHY_MSG,
)
from servicelib.rabbitmq import RabbitMQClient, RabbitMQRPCClient
from servicelib.redis import RedisClientSDK

from ._dependencies import (
    get_rabbitmq_client_from_request,
    get_rabbitmq_rpc_server_from_request,
    get_redis_client_from_request,
)

router = APIRouter()


class HealthCheckError(RuntimeError):
    """Failed a health check"""


@router.get("/", response_class=PlainTextResponse)
async def healthcheck(
    rabbit_client: Annotated[RabbitMQClient, Depends(get_rabbitmq_client_from_request)],
    rabbit_rpc_server: Annotated[
        RabbitMQRPCClient, Depends(get_rabbitmq_rpc_server_from_request)
    ],
    redis_client_sdk: Annotated[RedisClientSDK, Depends(get_redis_client_from_request)],
):
    if not rabbit_client.healthy or not rabbit_rpc_server.healthy:
        raise HealthCheckError(RABBITMQ_CLIENT_UNHEALTHY_MSG)

    if not redis_client_sdk.is_healthy:
        raise HealthCheckError(REDIS_CLIENT_UNHEALTHY_MSG)

    return f"{__name__}@{arrow.utcnow().isoformat()}"
