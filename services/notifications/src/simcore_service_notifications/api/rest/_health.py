from typing import Annotated

import arrow
from fastapi import APIRouter, Depends
from fastapi.responses import PlainTextResponse
from models_library.errors import (
    POSRGRES_DATABASE_UNHEALTHY_MSG,
    RABBITMQ_CLIENT_UNHEALTHY_MSG,
    REDIS_CLIENT_UNHEALTHY_MSG,
)
from models_library.healthchecks import IsNonResponsive, LivenessResult
from servicelib.fastapi.health import HealthCheckError
from servicelib.rabbitmq import RabbitMQClient
from servicelib.redis import RedisClientSDK

from .dependencies import get_postgres_liveness, get_rabbitmq_rpc_client, get_redis_client

router = APIRouter()


@router.get("/", response_class=PlainTextResponse)
async def check_service_health(
    rabbitmq_client: Annotated[RabbitMQClient, Depends(get_rabbitmq_rpc_client)],
    postgres_liveness: Annotated[LivenessResult, Depends(get_postgres_liveness)],
    redis_client_sdk: Annotated[RedisClientSDK, Depends(get_redis_client)],
) -> str:
    if not redis_client_sdk.is_healthy:
        raise HealthCheckError(REDIS_CLIENT_UNHEALTHY_MSG)

    if not rabbitmq_client.healthy:
        raise HealthCheckError(RABBITMQ_CLIENT_UNHEALTHY_MSG)

    if isinstance(postgres_liveness, IsNonResponsive):
        raise HealthCheckError(POSRGRES_DATABASE_UNHEALTHY_MSG)

    return f"{__name__}@{arrow.utcnow().datetime.isoformat()}"
