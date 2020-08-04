import logging
import pdb
import urllib.parse
from typing import List, Set, Tuple

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import ValidationError, constr
from pydantic.types import PositiveInt

from ...db.repositories.groups import GroupsRepository
from ...db.repositories.services import ServicesRepository
from ...models.domain.service import KEY_RE, VERSION_RE
from ...models.schemas.service import ServiceOut
from ..dependencies.database import get_repository
from ..dependencies.director import AuthSession, get_director_session

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("", response_model=List[ServiceOut])
async def list_services(
    user_id: PositiveInt,
    director_client: AuthSession = Depends(get_director_session),
    groups_repository: GroupsRepository = Depends(get_repository(GroupsRepository)),
    services_repo: ServicesRepository = Depends(get_repository(ServicesRepository)),
):
    # get user groups
    user_groups = await groups_repository.list_user_groups(user_id)
    # now get the allowed services
    allowed_services: Set[Tuple[str, str]] = {
        (service.key, service.version)
        for service in await services_repo.list_services(
            gids=[group.gid for group in user_groups], execute_access=True
        )
    }

    # get the services from the registry
    data = await director_client.get("/services")
    services: List[ServiceOut] = []
    for x in data:
        try:
            service = ServiceOut.parse_obj(x)
            if (service.key, service.version) in allowed_services:
                services.append(service)
        # services = parse_obj_as(List[ServiceOut], data)
        except ValidationError as exc:
            logger.warning(
                "skip service %s:%s that has invalid fields\n%s",
                x["key"],
                x["version"],
                exc,
            )

    return services


@router.get("/{service_key:path}/{service_version}", response_model=ServiceOut)
async def get_service(
    user_id: int,
    service_key: constr(regex=KEY_RE),
    service_version: constr(regex=VERSION_RE),
    director_client: AuthSession = Depends(get_director_session),
    groups_repository: GroupsRepository = Depends(get_repository(GroupsRepository)),
    services_repo: ServicesRepository = Depends(get_repository(ServicesRepository)),
):
    # check the service exists
    services_in_registry = await director_client.get(
        f"/services/{urllib.parse.quote_plus(service_key)}/{service_version}"
    )
    # the director client already raises an exception if not found

    # get user groups
    user_groups = await groups_repository.list_user_groups(user_id)
    # now check the user has execute access on the service
    service_in_db = await services_repo.get_service(
        service_key,
        service_version,
        gids=[group.gid for group in user_groups],
        execute_access=True,
    )
    if not service_in_db:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You have insufficient rights to access the service",
        )
    # access is allowed

    return ServiceOut.parse_obj(services_in_registry[0])


@router.patch("/{service_key:path}/{service_version}", response_model=ServiceOut)
async def modify_service(
    user_id: int,
    service_key: constr(regex=KEY_RE),
    service_version: constr(regex=VERSION_RE),
    groups_repository: GroupsRepository = Depends(get_repository(GroupsRepository)),
    services_repo: ServicesRepository = Depends(get_repository(ServicesRepository)),
):
    pass
