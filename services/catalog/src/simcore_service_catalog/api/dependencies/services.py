from fastapi.requests import Request

from ...core.settings import AppSettings
from ...models.schemas.services import ServiceResourcesGet


def get_default_service_resources(request: Request) -> ServiceResourcesGet:
    app_settings: AppSettings = request.app.state.settings
    return ServiceResourcesGet.construct(
        **app_settings.CATALOG_SERVICES_DEFAULT_RESOURCE.dict()
    )
