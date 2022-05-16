from fastapi.requests import Request
from models_library.services_resources import ServiceResources

from ...core.settings import AppSettings
from ...models.schemas.services_specifications import ServiceSpecifications


def get_default_service_resources(request: Request) -> ServiceResources:
    app_settings: AppSettings = request.app.state.settings
    return app_settings.CATALOG_SERVICES_DEFAULT_RESOURCE


def get_default_service_specifications(request: Request) -> ServiceSpecifications:
    app_settings: AppSettings = request.app.state.settings
    return app_settings.CATALOG_SERVICES_DEFAULT_SPECIFICATIONS
