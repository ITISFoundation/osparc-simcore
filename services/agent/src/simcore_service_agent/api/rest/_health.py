from typing import Annotated

import arrow
from fastapi import APIRouter, Depends, HTTPException, status
from models_library.api_schemas__common.health import HealthCheckGet
from models_library.errors import RABBITMQ_CLIENT_UNHEALTHY_MSG
from servicelib.rabbitmq import RabbitMQRPCClient

from ._dependencies import get_rabbitmq_rpc_client

router = APIRouter()


@router.get("/health", response_model=HealthCheckGet)
async def check_service_health(
    rabbitmq_rpc_client: Annotated[RabbitMQRPCClient, Depends(get_rabbitmq_rpc_client)],
):
    if not rabbitmq_rpc_client.healthy:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=RABBITMQ_CLIENT_UNHEALTHY_MSG,
        )

    return HealthCheckGet(timestamp=f"{__name__}@{arrow.utcnow().datetime.isoformat()}")
