from typing import Annotated

from fastapi import APIRouter, Depends, FastAPI, HTTPException, status

from ..models.schemas.application_health import ApplicationHealth
from ..modules.health_check import is_healthy
from ._dependencies import get_application

router = APIRouter()


@router.get(
    "/health",
    response_model=ApplicationHealth,
    responses={
        status.HTTP_503_SERVICE_UNAVAILABLE: {"description": "Service is unhealthy"}
    },
)
async def health_endpoint(
    app: Annotated[FastAPI, Depends(get_application)],
) -> ApplicationHealth:
    health_report = await is_healthy(app)
    if not health_report.is_healthy:
        application_health = ApplicationHealth(
            is_healthy=False,
            error_message=(
                "Registered health checks status: "
                f"ok_checks={health_report.ok_checks} "
                f"failing_checks={health_report.failing_checks}"
            ),
        )
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, detail=application_health.dict()
        )
    return ApplicationHealth()
