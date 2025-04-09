from typing import Annotated

import arrow
from fastapi import APIRouter, Depends
from models_library.api_schemas__common.health import HealthCheckGet
from models_library.errors import (
    POSRGRES_DATABASE_UNHEALTHY_MSG,
    RABBITMQ_CLIENT_UNHEALTHY_MSG,
)
from servicelib.rabbitmq import RabbitMQClient

from ...core.dependencies import get_postgress_health, get_rabbitmq_client
from ...services.postgres import PostgresHealth

router = APIRouter()


class HealthCheckError(RuntimeError):
    """Failed a health check"""


@router.get("/health", response_model=HealthCheckGet)
async def check_service_health(
    rabbitmq_client: Annotated[RabbitMQClient, Depends(get_rabbitmq_client)],
    posrgress_health: Annotated[PostgresHealth, Depends(get_postgress_health)],
):
    if not rabbitmq_client.healthy:
        raise HealthCheckError(RABBITMQ_CLIENT_UNHEALTHY_MSG)

    if not posrgress_health.is_responsive:
        raise HealthCheckError(POSRGRES_DATABASE_UNHEALTHY_MSG)

    return HealthCheckGet(timestamp=f"{__name__}@{arrow.utcnow().datetime.isoformat()}")
