from typing import Annotated

from fastapi import APIRouter, Depends, Header
from models_library.groups import GroupAtDB
from models_library.services import ServiceKey, ServiceVersion
from models_library.services_resources import ResourcesDict, ServiceResourcesDict

from ..._constants import RESPONSE_MODEL_POLICY
from ...clients.director import DirectorClient
from ...repository.services import ServicesRepository
from ...service.services_resources import get_catalog_service_resources
from .._dependencies.director import get_director_client
from .._dependencies.repository import get_repository
from .._dependencies.services import get_default_service_resources
from .._dependencies.user_groups import list_user_groups

router = APIRouter()


@router.get(
    "/{service_key:path}/{service_version}/resources",
    response_model=ServiceResourcesDict,
    **RESPONSE_MODEL_POLICY,
)
async def get_service_resources(
    service_key: ServiceKey,
    service_version: ServiceVersion,
    director_client: Annotated[DirectorClient, Depends(get_director_client)],
    default_service_resources: Annotated[ResourcesDict, Depends(get_default_service_resources)],
    services_repo: Annotated[ServicesRepository, Depends(get_repository(ServicesRepository))],
    user_groups: Annotated[list[GroupAtDB], Depends(list_user_groups)],
    x_simcore_products_name: Annotated[str, Header(...)],
) -> ServiceResourcesDict:
    return await get_catalog_service_resources(
        director_client,
        services_repo,
        default_service_resources=default_service_resources,
        user_groups=user_groups,
        product_name=x_simcore_products_name,
        service_key=service_key,
        service_version=service_version,
    )
