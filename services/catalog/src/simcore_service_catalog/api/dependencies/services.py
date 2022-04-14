from fastapi.requests import Request
from models_library.services import ServiceResources

from ...core.settings import AppSettings


def get_default_service_resources(request: Request) -> ServiceResources:
    app_settings: AppSettings = request.app.state.settings
    return ServiceResources(
        limits=app_settings.CATALOG_SERVICES_DEFAULT_LIMITS,
        reservations=app_settings.CATALOG_SERVICES_DEFAULT_RESERVATIONS,
    )
