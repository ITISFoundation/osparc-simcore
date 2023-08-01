import logging
import urllib.parse
from dataclasses import dataclass
from typing import Any, cast

from fastapi import Depends, Header, HTTPException, status
from fastapi.requests import Request
from models_library.api_schemas_catalog.services import ServiceGet
from models_library.api_schemas_catalog.services_specifications import (
    ServiceSpecifications,
)
from models_library.services import ServiceKey, ServiceVersion
from models_library.services_resources import ResourcesDict
from pydantic import ValidationError

from ...core.settings import ApplicationSettings
from ...db.repositories.groups import GroupsRepository
from ...db.repositories.services import ServicesRepository
from ...services.director import DirectorApi
from ...services.function_services import get_function_service, is_function_service
from .database import get_repository
from .director import get_director_api


def get_default_service_resources(request: Request) -> ResourcesDict:
    app_settings: ApplicationSettings = request.app.state.settings
    return app_settings.CATALOG_SERVICES_DEFAULT_RESOURCES


def get_default_service_specifications(request: Request) -> ServiceSpecifications:
    app_settings: ApplicationSettings = request.app.state.settings
    return app_settings.CATALOG_SERVICES_DEFAULT_SPECIFICATIONS


@dataclass(frozen=True)
class AccessInfo:
    uid: int
    gid: list[int]
    product: str


async def check_service_read_access(
    user_id: int,
    service_key: ServiceKey,
    service_version: ServiceVersion,
    groups_repository: GroupsRepository = Depends(get_repository(GroupsRepository)),
    services_repo: ServicesRepository = Depends(get_repository(ServicesRepository)),
    x_simcore_products_name: str = Header(None),
) -> AccessInfo:
    # get the user's groups
    user_groups = await groups_repository.list_user_groups(user_id)
    if not user_groups:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You have unsufficient rights to access the service",
        )

    # check the user has access to this service and to which extent
    if not await services_repo.get_service(
        service_key,
        service_version,
        gids=[group.gid for group in user_groups],
        product_name=x_simcore_products_name,
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot access this service. It is either not published or not exposed to this user.",
        )

    return AccessInfo(
        uid=user_id,
        gid=[group.gid for group in user_groups],
        product=x_simcore_products_name,
    )


logger = logging.getLogger(__name__)


async def get_service_from_registry(
    service_key: ServiceKey,
    service_version: ServiceVersion,
    director_client: DirectorApi = Depends(get_director_api),
) -> ServiceGet:
    """
    Retrieves service metadata from the docker registry via the director
    """
    try:
        if is_function_service(service_key):
            frontend_service: dict[str, Any] = get_function_service(
                key=service_key, version=service_version
            )
            _service_data = frontend_service
        else:
            # NOTE: raises HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE) on ANY failure
            services_in_registry = cast(
                list[Any],
                await director_client.get(
                    f"/services/{urllib.parse.quote_plus(service_key)}/{service_version}"
                ),
            )
            _service_data = services_in_registry[0]

        service: ServiceGet = ServiceGet.parse_obj(_service_data)
        return service

    except ValidationError as exc:
        logger.warning(
            "Invalid service metadata in registry. Audit registry data for %s %s",
            f"{service_key=}",
            f"{service_version=}",
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Service {service_key}:{service_version} not found",
        ) from exc
