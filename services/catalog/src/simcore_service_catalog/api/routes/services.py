import logging
import urllib.parse
from typing import List, Optional, Set, Tuple

# FIXME: too many DB calls
from fastapi import APIRouter, Depends, Header, HTTPException, status
from models_library.services import (
    KEY_RE,
    VERSION_RE,
    ServiceAccessRightsAtDB,
    ServiceMetaDataAtDB,
    ServiceType,
)
from pydantic import ValidationError, constr
from pydantic.types import PositiveInt

from ...db.repositories.groups import GroupsRepository
from ...db.repositories.services import ServicesRepository
from ...models.schemas.services import ServiceOut, ServiceUpdate
from ...services.frontend_services import get_services as get_frontend_services
from ..dependencies.database import get_repository
from ..dependencies.director import DirectorApi, get_director_api

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("", response_model=List[ServiceOut])
async def list_services(
    # pylint: disable=too-many-arguments
    user_id: PositiveInt,
    details: Optional[bool] = True,
    director_client: DirectorApi = Depends(get_director_api),
    groups_repository: GroupsRepository = Depends(get_repository(GroupsRepository)),
    services_repo: ServicesRepository = Depends(get_repository(ServicesRepository)),
    x_simcore_products_name: str = Header(...),
):
    # get user groups
    user_groups = await groups_repository.list_user_groups(user_id)
    if not user_groups:
        # deny access
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You have unsufficient rights to access the services",
        )
    # now get the executable services
    executable_services: Set[Tuple[str, str]] = {
        (service.key, service.version)
        for service in await services_repo.list_services(
            gids=[group.gid for group in user_groups],
            execute_access=True,
            product_name=x_simcore_products_name,
        )
    }
    # get the writable services
    _services = await services_repo.list_services(
        gids=[group.gid for group in user_groups],
        write_access=True,
        product_name=x_simcore_products_name,
    )
    writable_services: Set[Tuple[str, str]] = {
        (service.key, service.version) for service in _services
    }
    visible_services = executable_services | writable_services
    if not details:
        # only return a stripped down version
        services = [
            ServiceOut(
                key=key,
                version=version,
                name="nodetails",
                description="nodetails",
                type=ServiceType.COMPUTATIONAL,
                authors=[{"name": "nodetails", "email": "nodetails@nodetails.com"}],
                contact="nodetails@nodetails.com",
                inputs={},
                outputs={},
            )
            for key, version in visible_services
        ]
        return services

    # get the services from the registry and filter them out
    frontend_services = [s.dict(by_alias=True) for s in get_frontend_services()]
    registry_services = await director_client.get("/services")
    data = frontend_services + registry_services
    services: List[ServiceOut] = []
    for x in data:
        try:
            service = ServiceOut.parse_obj(x)

            if not (service.key, service.version) in visible_services:
                # no access to that service
                continue

            # we have write access for that service, fill in the service rights
            access_rights: List[
                ServiceAccessRightsAtDB
            ] = await services_repo.get_service_access_rights(
                service.key, service.version, product_name=x_simcore_products_name
            )
            service.access_rights = {rights.gid: rights for rights in access_rights}

            # access is allowed, override some of the values with what is in the db
            service_in_db: Optional[
                ServiceMetaDataAtDB
            ] = await services_repo.get_service(service.key, service.version)
            if not service_in_db:
                logger.error(
                    "The service %s:%s is not in the database",
                    service.key,
                    service.version,
                )
                continue
            service = service.copy(
                update=service_in_db.dict(exclude_unset=True, exclude={"owner"})
            )
            # the owner shall be converted to an email address
            if service_in_db.owner:
                service.owner = await groups_repository.get_user_email_from_gid(
                    service_in_db.owner
                )

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
    # pylint: disable=too-many-arguments
    user_id: int,
    service_key: constr(regex=KEY_RE),
    service_version: constr(regex=VERSION_RE),
    director_client: DirectorApi = Depends(get_director_api),
    groups_repository: GroupsRepository = Depends(get_repository(GroupsRepository)),
    services_repo: ServicesRepository = Depends(get_repository(ServicesRepository)),
    x_simcore_products_name: str = Header(None),
):
    # check the service exists
    services_in_registry = await director_client.get(
        f"/services/{urllib.parse.quote_plus(service_key)}/{service_version}"
    )
    service = ServiceOut.parse_obj(services_in_registry[0])
    # the director client already raises an exception if not found

    # get the user groups
    user_groups = await groups_repository.list_user_groups(user_id)
    if not user_groups:
        # deny access
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You have unsufficient rights to access the service",
        )
    # check the user has access to this service and to which extent
    service_in_db = await services_repo.get_service(
        service_key,
        service_version,
        gids=[group.gid for group in user_groups],
        write_access=True,
        product_name=x_simcore_products_name,
    )
    if service_in_db:
        # we have full access, let's add the access to the output
        service_access_rights: List[
            ServiceAccessRightsAtDB
        ] = await services_repo.get_service_access_rights(
            service.key, service.version, product_name=x_simcore_products_name
        )
        service.access_rights = {rights.gid: rights for rights in service_access_rights}
    else:
        # check if we have executable rights
        service_in_db = await services_repo.get_service(
            service_key,
            service_version,
            gids=[group.gid for group in user_groups],
            execute_access=True,
            product_name=x_simcore_products_name,
        )
        if not service_in_db:
            # we have no access here
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You have insufficient rights to access the service",
            )
    # access is allowed, override some of the values with what is in the db
    service = service.copy(
        update=service_in_db.dict(exclude_unset=True, exclude={"owner"})
    )
    # the owner shall be converted to an email address
    if service_in_db.owner:
        service.owner = await groups_repository.get_user_email_from_gid(
            service_in_db.owner
        )

    return service


@router.patch("/{service_key:path}/{service_version}", response_model=ServiceOut)
async def modify_service(
    # pylint: disable=too-many-arguments
    user_id: int,
    service_key: constr(regex=KEY_RE),
    service_version: constr(regex=VERSION_RE),
    updated_service: ServiceUpdate,
    director_client: DirectorApi = Depends(get_director_api),
    groups_repository: GroupsRepository = Depends(get_repository(GroupsRepository)),
    services_repo: ServicesRepository = Depends(get_repository(ServicesRepository)),
    x_simcore_products_name: str = Header(None),
):
    # check the service exists
    await director_client.get(
        f"/services/{urllib.parse.quote_plus(service_key)}/{service_version}"
    )
    # the director client already raises an exception if not found

    # get the user groups
    user_groups = await groups_repository.list_user_groups(user_id)
    if not user_groups:
        # deny access
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You have unsufficient rights to access the service",
        )
    # check the user has write access to this service
    writable_service = await services_repo.get_service(
        service_key,
        service_version,
        gids=[group.gid for group in user_groups],
        write_access=True,
        product_name=x_simcore_products_name,
    )
    if not writable_service:
        # deny access
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You have unsufficient rights to modify the service",
        )

    # let's modify the service then
    await services_repo.update_service(
        ServiceMetaDataAtDB(
            key=service_key,
            version=service_version,
            **updated_service.dict(exclude_unset=True),
        )
    )
    # let's modify the service access rights (they can be added/removed/modified)
    current_gids_in_db = [
        r.gid
        for r in await services_repo.get_service_access_rights(
            service_key, service_version, product_name=x_simcore_products_name
        )
    ]

    if updated_service.access_rights:
        # start by updating/inserting new entries
        new_access_rights = [
            ServiceAccessRightsAtDB(
                key=service_key,
                version=service_version,
                gid=gid,
                execute_access=rights.execute_access,
                write_access=rights.write_access,
                product_name=x_simcore_products_name,
            )
            for gid, rights in updated_service.access_rights.items()
        ]
        await services_repo.upsert_service_access_rights(new_access_rights)

        # then delete the ones that were removed
        removed_gids = [
            gid
            for gid in current_gids_in_db
            if gid not in updated_service.access_rights
        ]
        deleted_access_rights = [
            ServiceAccessRightsAtDB(
                key=service_key,
                version=service_version,
                gid=gid,
                product_name=x_simcore_products_name,
            )
            for gid in removed_gids
        ]
        await services_repo.delete_service_access_rights(deleted_access_rights)

    # now return the service
    return await get_service(
        user_id,
        service_key,
        service_version,
        director_client,
        groups_repository,
        services_repo,
        x_simcore_products_name,
    )
