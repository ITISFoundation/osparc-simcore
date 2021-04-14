from fastapi import APIRouter, Request, Response

from ..models import ApplicationHealth

health_router = APIRouter()


@health_router.get("/health", response_model=ApplicationHealth)
async def health_endpoint(request: Request, response: Response) -> ApplicationHealth:
    application_health: ApplicationHealth = request.app.state.application_health

    if application_health.is_healty is False:
        response.status_code = 400

    return application_health


__all__ = ["health_router"]
