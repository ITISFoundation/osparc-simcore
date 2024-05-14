from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from models_library.errors import RABBITMQ_CLIENT_UNHEALTHY_MSG
from servicelib.rabbitmq import RabbitMQClient

from ..models.schemas.application_health import ApplicationHealth
from ._dependencies import get_application_health, get_rabbitmq_client

router = APIRouter()


@router.get(
    "/health",
    response_model=ApplicationHealth,
    responses={
        status.HTTP_503_SERVICE_UNAVAILABLE: {"description": "Service is unhealthy"}
    },
)
async def health_endpoint(
    application_health: Annotated[ApplicationHealth, Depends(get_application_health)],
    rabbitmq_client: Annotated[RabbitMQClient, Depends(get_rabbitmq_client)],
) -> ApplicationHealth:
    if not application_health.is_healthy:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, detail=application_health.dict()
        )

    if not rabbitmq_client.healthy:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, detail=RABBITMQ_CLIENT_UNHEALTHY_MSG
        )

    return application_health
