import logging
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
    ServiceAccessRightsAtDB,
    ServiceMetaDataAtDB,
)
from ...models.schemas.service import ServiceIn, ServiceOut
from ..dependencies.database import get_repository
from ..dependencies.director import AuthSession, get_director_session

router = APIRouter()
logger = logging.getLogger(__name__)

# FIXME: too many DB calls
SERVICE_OVERRIDEN_VARIABLES = ["name", "description", "thumbnail"]


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
    # get the services from the registry and filter them out
    data = await director_client.get("/services")
    services: List[ServiceOut] = []
    for x in data:
        try:
            service = ServiceOut.parse_obj(x)

            if (
                not (service.key, service.version) in writable_services
                and not (service.key, service.version) in executable_services
            ):
                # no access to that service
                continue

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

            # access is allowed, override some of the values with what is in the db
            service_in_db = await services_repo.get_service(
                service.key, service.version
            )
            for attr in SERVICE_OVERRIDEN_VARIABLES:
                setattr(service, attr, getattr(service_in_db, attr))
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
    service_in_db = await services_repo.get_service(
        service_key,
        service_version,
        gids=[group.gid for group in user_groups],
        write_access=True,
    )
    if service_in_db:
        # we have full access, let's add the access to the output
        service_access_rights: List[
            ServiceAccessRightsAtDB
        ] = await services_repo.get_service_access_rights(service.key, service.version)
        service.access_rights = {rights.gid: rights for rights in service_access_rights}
    else:
        # check if we have executable rights
        service_in_db = await services_repo.get_service(
            service_key,
            service_version,
            gids=[group.gid for group in user_groups],
            execute_access=True,
        )
        if not service_in_db:
            # we have no access here
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You have insufficient rights to access the service",
            )
    # access is allowed, override some of the values with what is in the db
    for attr in SERVICE_OVERRIDEN_VARIABLES:
        setattr(service, attr, getattr(service_in_db, attr))

    return service


@router.patch("/{service_key:path}/{service_version}", response_model=ServiceOut)
async def modify_service(
    user_id: int,
    service_key: constr(regex=KEY_RE),
    service_version: constr(regex=VERSION_RE),
    updated_service: ServiceIn,
    director_client: AuthSession = Depends(get_director_session),
    groups_repository: GroupsRepository = Depends(get_repository(GroupsRepository)),
    services_repo: ServicesRepository = Depends(get_repository(ServicesRepository)),
):
    # check the service exists
    await director_client.get(
        f"/services/{urllib.parse.quote_plus(service_key)}/{service_version}"
    )
    # the director client already raises an exception if not found

    # get the user groups
    user_groups = await groups_repository.list_user_groups(user_id)
    # check the user has write access to this service
    writable_service = await services_repo.get_service(
        service_key,
        service_version,
        gids=[group.gid for group in user_groups],
        write_access=True,
    )
    if not writable_service:
        # deny access
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You have unsufficient rights to modify the service",
        )

    # let's modify the service then
    partial_updated_service = ServiceMetaDataAtDB(
        key=service_key,
        version=service_version,
        **updated_service.dict(exclude_unset=True),
    )
    partial_updated_rights = [
        ServiceAccessRightsAtDB(
            key=service_key,
            version=service_version,
            gid=gid,
            execute_access=rights.execute_access,
            write_access=rights.write_access,
        )
        for gid, rights in updated_service.access_rights.items()
    ]
    await services_repo.update_service(partial_updated_service, partial_updated_rights)

    # now return the service
    return await get_service(
        user_id,
        service_key,
        service_version,
        director_client,
        groups_repository,
        services_repo,
    )
