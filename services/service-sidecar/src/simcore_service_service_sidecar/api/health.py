from fastapi import APIRouter, Request
from ..models import ApplicationHealth

health_router = APIRouter()


@health_router.get("/health", response_model=ApplicationHealth)
async def health_endpoint(request: Request) -> ApplicationHealth:
    return request.app.state.application_health


__all__ = ["health_router"]