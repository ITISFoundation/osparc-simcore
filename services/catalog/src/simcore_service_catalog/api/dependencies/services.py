from fastapi.requests import Request
from models_library.services_resources import Resources

from ...core.settings import AppSettings


def get_default_service_resources(request: Request) -> Resources:
    app_settings: AppSettings = request.app.state.settings
    return app_settings.CATALOG_SERVICES_DEFAULT_RESOURCES
