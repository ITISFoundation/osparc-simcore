import logging

from fastapi import APIRouter, Depends, Header
from models_library.api_schemas_catalog.service_access_rights import (
    ServiceAccessRightsGet,
)
from models_library.services import ServiceKey, ServiceVersion
from models_library.services_db import ServiceAccessRightsAtDB

from ...db.repositories.services import ServicesRepository
from ..dependencies.database import get_repository
from ..dependencies.services import AccessInfo, check_service_read_access
from ._constants import RESPONSE_MODEL_POLICY

#
# Routes -----------------------------------------------------------------------------------------------
#

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get(
    "/{service_key:path}/{service_version}/accessRights",
    response_model=ServiceAccessRightsGet,
    description="Returns access rights information for provided service and product",
    **RESPONSE_MODEL_POLICY,
)
async def get_service_access_rights(
    service_key: ServiceKey,
    service_version: ServiceVersion,
    _user: AccessInfo = Depends(check_service_read_access),
    services_repo: ServicesRepository = Depends(get_repository(ServicesRepository)),
    x_simcore_products_name: str = Header(...),
):
    service_access_rights: list[
        ServiceAccessRightsAtDB
    ] = await services_repo.get_service_access_rights(
        key=service_key, version=service_version, product_name=x_simcore_products_name
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
