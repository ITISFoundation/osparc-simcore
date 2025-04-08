import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Header
from models_library.api_schemas_catalog.service_access_rights import (
    ServiceAccessRightsGet,
)
from models_library.services import ServiceKey, ServiceVersion

from ..._constants import RESPONSE_MODEL_POLICY
from ...db.repositories.services import ServicesRepository
from ...models.services_db import ServiceAccessRightsAtDB
from .._dependencies.database import get_repository
from .._dependencies.services import AccessInfo, check_service_read_access

_logger = logging.getLogger(__name__)

router = APIRouter()


@router.get(
    "/{service_key:path}/{service_version}/accessRights",
    response_model=ServiceAccessRightsGet,
    description="Returns access rights information for provided service and product",
    **RESPONSE_MODEL_POLICY,
)
async def get_service_access_rights(
    service_key: ServiceKey,
    service_version: ServiceVersion,
    _user: Annotated[AccessInfo, Depends(check_service_read_access)],
    services_repo: Annotated[
        ServicesRepository, Depends(get_repository(ServicesRepository))
    ],
    x_simcore_products_name: Annotated[str, Header(...)],
):
    service_access_rights: list[ServiceAccessRightsAtDB] = (
        await services_repo.get_service_access_rights(
            key=service_key,
            version=service_version,
            product_name=x_simcore_products_name,
        )
    )

    gids_with_access_rights = {}
    for s in service_access_rights:
        gids_with_access_rights[s.gid] = {
            "execute_access": s.execute_access,
            "write_access": s.write_access,
        }

    return ServiceAccessRightsGet(
        service_key=service_key,
        service_version=service_version,
        gids_with_access_rights=gids_with_access_rights,
    )
