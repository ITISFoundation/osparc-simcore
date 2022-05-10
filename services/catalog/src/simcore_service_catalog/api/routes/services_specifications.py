import logging

from fastapi import APIRouter, Depends, HTTPException, status
from models_library.services import ServiceKey, ServiceVersion
from models_library.users import UserID

from ...db.repositories.groups import GroupsRepository
from ...db.repositories.services import ServicesRepository
from ...models.schemas.constants import RESPONSE_MODEL_POLICY
from ...models.schemas.services_specifications import ServiceSpecificationsGet
from ..dependencies.database import get_repository

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get(
    "/{service_key:path}/{service_version}/specifications",
    response_model=ServiceSpecificationsGet,
    **RESPONSE_MODEL_POLICY,
)
# @cached(
#     ttl=DIRECTOR_CACHING_TTL,
#     key_builder=lambda f, *args, **kwargs: f"{f.__name__}_{kwargs['service_key']}_{kwargs['service_version']}",
# )
async def get_service_specifications(
    user_id: UserID,
    service_key: ServiceKey,
    service_version: ServiceVersion,
    groups_repository: GroupsRepository = Depends(get_repository(GroupsRepository)),
    services_repo: ServicesRepository = Depends(get_repository(ServicesRepository)),
):
    logger.debug("getting specifications for '%s:%s'", service_key, service_version)
    # Access layer
    user_groups = await groups_repository.list_user_groups(user_id)
    if not user_groups:
        # deny access, but this should not happen
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You have unsufficient rights to access the services",
        )

    service_specs = await services_repo.get_service_specifications(
        service_key, service_version, tuple(user_groups)
    )
    return service_specs
