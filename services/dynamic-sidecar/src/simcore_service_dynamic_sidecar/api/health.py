from fastapi import APIRouter, Depends, HTTPException, status

from ..dependencies import get_application_health
from ..models import ApplicationHealth

health_router = APIRouter()


@health_router.get(
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
            status.HTTP_503_SERVICE_UNAVAILABLE, detail="Marked as unhealthy"
        )

    return application_health


__all__ = ["health_router"]
