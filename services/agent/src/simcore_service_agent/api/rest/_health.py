from typing import Annotated

import arrow
from fastapi import APIRouter, Depends
from models_library.api_schemas__common.health import HealthCheckGet
from models_library.errors import RABBITMQ_CLIENT_UNHEALTHY_MSG
from servicelib.rabbitmq import RabbitMQRPCClient

from ._dependencies import get_rabbitmq_rpc_client

router = APIRouter()


class HealthCheckError(RuntimeError):
    """Failed a health check"""


@router.get("/health", response_model=HealthCheckGet)
async def check_service_health(
    rabbitmq_rpc_client: Annotated[RabbitMQRPCClient, Depends(get_rabbitmq_rpc_client)],
):
    if not rabbitmq_rpc_client.healthy:
        raise HealthCheckError(RABBITMQ_CLIENT_UNHEALTHY_MSG)

    return HealthCheckGet(timestamp=f"{__name__}@{arrow.utcnow().datetime.isoformat()}")
