import urllib.parse
from typing import Any, cast

from fastapi import Depends, HTTPException, status
from fastapi.requests import Request
from models_library.services import ServiceKey, ServiceVersion
from models_library.services_resources import ResourcesDict

from ...core.settings import AppSettings
from ...models.schemas.services import ServiceGet
from ...models.schemas.services_specifications import ServiceSpecifications
from ...services.director import DirectorApi
from ...services.function_services import get_function_service, is_function_service
from .director import DirectorApi, get_director_api


def get_default_service_resources(request: Request) -> ResourcesDict:
    app_settings: AppSettings = request.app.state.settings
    return app_settings.CATALOG_SERVICES_DEFAULT_RESOURCES


def get_default_service_specifications(request: Request) -> ServiceSpecifications:
    app_settings: AppSettings = request.app.state.settings
    return app_settings.CATALOG_SERVICES_DEFAULT_SPECIFICATIONS


async def get_service_from_registry(
    service_key: ServiceKey,
    service_version: ServiceVersion,
    director_client: DirectorApi = Depends(get_director_api),
) -> ServiceGet:
    """
    Retrieves service metadata
    """
    try:
        if is_function_service(service_key):
            frontend_service: dict[str, Any] = get_function_service(
                key=service_key, version=service_version
            )
            _service_data = frontend_service
        else:
            # FIXME: what if error?
            services_in_registry = cast(
                list[Any],
                await director_client.get(
                    f"/services/{urllib.parse.quote_plus(service_key)}/{service_version}"
                ),
            )
            _service_data = services_in_registry[0]

        service: ServiceGet = ServiceGet.parse_obj(_service_data)
        return service

    except HTTPException:
        raise
    except Exception as exc:  # FIXME: ValidationERror, director_clietn exceptions?
        # All HTTPExceptions get handled by http_error_handler
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Service {service_key}:{service_version} not found",
        ) from exc
