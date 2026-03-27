from typing import Annotated

import arrow
from fastapi import APIRouter, Depends
from models_library.api_schemas__common.health import HealthCheckGet
from models_library.errors import (
    POSRGRES_DATABASE_UNHEALTHY_MSG,
    RABBITMQ_CLIENT_UNHEALTHY_MSG,
    REDIS_CLIENT_UNHEALTHY_MSG,
)
from servicelib.rabbitmq import RabbitMQClient
from servicelib.redis import RedisClientSDK

from ...clients.postgres import PostgresLiveness
from .dependencies import get_postgres_liveness, get_rabbitmq_rpc_client, get_redis_client_from_request

router = APIRouter()


class HealthCheckError(RuntimeError):
    """Failed a health check"""


@router.get("/", response_model=HealthCheckGet)
async def check_service_health(
    rabbitmq_client: Annotated[RabbitMQClient, Depends(get_rabbitmq_rpc_client)],
    postgres_liveness: Annotated[PostgresLiveness, Depends(get_postgres_liveness)],
    redis_client_sdk: Annotated[RedisClientSDK, Depends(get_redis_client_from_request)],
) -> HealthCheckGet:
    if not redis_client_sdk.is_healthy:
        raise HealthCheckError(REDIS_CLIENT_UNHEALTHY_MSG)

    if not rabbitmq_client.healthy:
        raise HealthCheckError(RABBITMQ_CLIENT_UNHEALTHY_MSG)

    if not postgres_liveness.is_responsive:
        raise HealthCheckError(POSRGRES_DATABASE_UNHEALTHY_MSG)

    return HealthCheckGet(timestamp=f"{__name__}@{arrow.utcnow().datetime.isoformat()}")
