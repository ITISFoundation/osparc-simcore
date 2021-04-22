from fastapi import APIRouter, Depends, HTTPException, status

from ..dependencies import State, get_app_state
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
    app_state: State = Depends(get_app_state),
):
    application_health: ApplicationHealth = app_state.application_health

    if not application_health.is_healthy:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, detail="Marked as unhealthy"
        )

    return application_health


__all__ = ["health_router"]
