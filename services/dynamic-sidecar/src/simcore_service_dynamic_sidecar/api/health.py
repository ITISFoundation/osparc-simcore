from fastapi import APIRouter, Depends, HTTPException, status

from ..models.schemas.application_health import ApplicationHealth
from ._dependencies import get_application_health

router = APIRouter()


@router.get(
    "/health",
    response_model=ApplicationHealth,
    responses={
        status.HTTP_503_SERVICE_UNAVAILABLE: {"description": "Service is unhealthy"}
    },
)
async def health_endpoint(
    application_health: ApplicationHealth = Depends(get_application_health),
) -> ApplicationHealth:
    if not application_health.is_healthy:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, detail=application_health.dict()
        )

    return application_health
