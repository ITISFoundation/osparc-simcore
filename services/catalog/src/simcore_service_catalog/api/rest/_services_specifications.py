import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from models_library.api_schemas_catalog.services_specifications import (
    ServiceSpecifications,
    ServiceSpecificationsGet,
)
from models_library.services import ServiceKey, ServiceVersion
from models_library.users import UserID

from ..._constants import RESPONSE_MODEL_POLICY
from ...db.repositories.groups import GroupsRepository
from ...db.repositories.services import ServicesRepository
from ...services.function_services import is_function_service
from ..dependencies.database import get_repository
from ..dependencies.services import get_default_service_specifications

router = APIRouter()
_logger = logging.getLogger(__name__)


@router.get(
    "/{service_key:path}/{service_version}/specifications",
    response_model=ServiceSpecificationsGet,
    **RESPONSE_MODEL_POLICY,
)
async def get_service_specifications(
    user_id: UserID,
    service_key: ServiceKey,
    service_version: ServiceVersion,
    groups_repository: Annotated[
        GroupsRepository, Depends(get_repository(GroupsRepository))
    ],
    services_repo: Annotated[
        ServicesRepository, Depends(get_repository(ServicesRepository))
    ],
    default_service_specifications: Annotated[
        ServiceSpecifications, Depends(get_default_service_specifications)
    ],
    *,
    strict: Annotated[
        bool,
        Query(
            description="if True only the version specs will be retrieved, if False the latest version will be used instead",
        ),
    ] = False,
):
    _logger.debug("getting specifications for '%s:%s'", service_key, service_version)

    if is_function_service(service_key):
        # There is no specification for these, return empty specs
        return ServiceSpecifications()

    # Access layer
    user_groups = await groups_repository.list_user_groups(user_id)
    if not user_groups:
        # deny access, but this should not happen
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You have unsufficient rights to access the services",
        )

    service_specs = await services_repo.get_service_specifications(
        service_key,
        service_version,
        tuple(user_groups),
        allow_use_latest_service_version=not strict,
    )

    if not service_specs:
        # nothing found, let's return the default then
        service_specs = default_service_specifications.model_copy()

    _logger.debug("returning %s", f"{service_specs=}")
    return service_specs
