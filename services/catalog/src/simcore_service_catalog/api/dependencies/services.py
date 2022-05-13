from fastapi.requests import Request
from models_library.services_resources import ResourcesDict

from ...core.settings import AppSettings


def get_default_service_resources(request: Request) -> ResourcesDict:
    app_settings: AppSettings = request.app.state.settings
    return app_settings.CATALOG_SERVICES_DEFAULT_RESOURCES
