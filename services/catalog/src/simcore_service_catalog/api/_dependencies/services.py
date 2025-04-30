import logging
from dataclasses import dataclass
from typing import Annotated, cast

from fastapi import Depends, FastAPI, Header, HTTPException, status
from models_library.api_schemas_catalog.services_specifications import (
    ServiceSpecifications,
)
from models_library.services_metadata_published import ServiceMetaDataPublished
from models_library.services_resources import ResourcesDict
from models_library.services_types import ServiceKey, ServiceVersion
from pydantic import ValidationError
from servicelib.fastapi.dependencies import get_app

from ...clients.director import DirectorClient
from ...core.settings import ApplicationSettings
from ...repository.groups import GroupsRepository
from ...repository.services import ServicesRepository
from ...service import manifest
from .director import get_director_client
from .repository import get_repository

_logger = logging.getLogger(__name__)


def get_default_service_resources(
    app: Annotated[FastAPI, Depends(get_app)],
) -> ResourcesDict:
    app_settings: ApplicationSettings = app.state.settings
    return app_settings.CATALOG_SERVICES_DEFAULT_RESOURCES


def get_default_service_specifications(
    app: Annotated[FastAPI, Depends(get_app)],
) -> ServiceSpecifications:
    app_settings: ApplicationSettings = app.state.settings
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
    groups_repository: Annotated[
        GroupsRepository, Depends(get_repository(GroupsRepository))
    ],
    services_repo: Annotated[
        ServicesRepository, Depends(get_repository(ServicesRepository))
    ],
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


async def get_service_from_manifest(
    service_key: ServiceKey,
    service_version: ServiceVersion,
    director_client: Annotated[DirectorClient, Depends(get_director_client)],
) -> ServiceMetaDataPublished:
    """
    Retrieves service metadata from the docker registry via the director
    """
    try:
        return cast(
            ServiceMetaDataPublished,
            await manifest.get_service(
                director_client=director_client,
                key=service_key,
                version=service_version,
            ),
        )

    except ValidationError as exc:
        _logger.warning(
            "Invalid service metadata in registry. Audit registry data for %s %s",
            f"{service_key=}",
            f"{service_version=}",
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Service {service_key}:{service_version} not found",
        ) from exc
