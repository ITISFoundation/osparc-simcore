import logging
from os import write
import pdb
import urllib.parse
from typing import List, Set, Tuple

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import ValidationError, constr
from pydantic.types import PositiveInt

from ...db.repositories.groups import GroupsRepository
from ...db.repositories.services import ServicesRepository
from ...models.domain.service import (
    KEY_RE,
    VERSION_RE,
    ServiceAccessRights,
    ServiceAccessRightsAtDB,
    ServiceDockerData,
)
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
    # now get the executable services
    executable_services: Set[Tuple[str, str]] = {
        (service.key, service.version)
        for service in await services_repo.list_services(
            gids=[group.gid for group in user_groups], execute_access=True
        )
    }
    # get the writable services
    writable_services: Set[Tuple[str, str]] = {
        (service.key, service.version)
        for service in await services_repo.list_services(
            gids=[group.gid for group in user_groups], write_access=True
        )
    }
    # get the services from the registry
    data = await director_client.get("/services")
    services: List[ServiceOut] = []
    for x in data:
        try:
            service = ServiceOut.parse_obj(x)
            if (service.key, service.version) in writable_services:
                # we have write access for that service, fill in the service rights
                service_access_rights: List[
                    ServiceAccessRightsAtDB
                ] = await services_repo.get_service_access_rights(
                    service.key, service.version
                )
                service.access_rights = {
                    rights.gid: rights for rights in service_access_rights
                }
                services.append(service)
            elif (service.key, service.version) in executable_services:
                services.append(service)

        # services = parse_obj_as(List[ServiceOut], data) this does not work since if one service has an issue it fails
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
    service = ServiceOut.parse_obj(services_in_registry[0])
    # the director client already raises an exception if not found

    # get the user groups
    user_groups = await groups_repository.list_user_groups(user_id)
    # check the user has access to this service and to which extent
    writable_service = await services_repo.get_service(
        service_key,
        service_version,
        gids=[group.gid for group in user_groups],
        write_access=True,
    )
    if writable_service:
        # we have full access, let's add the access to the output
        service_access_rights: List[
            ServiceAccessRightsAtDB
        ] = await services_repo.get_service_access_rights(service.key, service.version)
        service.access_rights = {rights.gid: rights for rights in service_access_rights}
        return service

    # check if we have executable rights
    executable_service = await services_repo.get_service(
        service_key,
        service_version,
        gids=[group.gid for group in user_groups],
        execute_access=True,
    )
    if not executable_service:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You have insufficient rights to access the service",
        )
    # access is allowed
    return service


@router.patch("/{service_key:path}/{service_version}", response_model=ServiceOut)
async def modify_service(
    user_id: int,
    service_key: constr(regex=KEY_RE),
    service_version: constr(regex=VERSION_RE),
    groups_repository: GroupsRepository = Depends(get_repository(GroupsRepository)),
    services_repo: ServicesRepository = Depends(get_repository(ServicesRepository)),
):
    pass
