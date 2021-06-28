# pylint: disable=too-many-arguments

import asyncio
import logging
import urllib.parse
from typing import Any, Dict, List, Optional, Set, Tuple

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
from starlette.requests import Request

from ...db.repositories.groups import GroupsRepository
from ...db.repositories.services import ServicesRepository
from ...models.schemas.services import ServiceOut, ServiceUpdate
from ...services.frontend_services import (
    get_frontend_service,
    is_frontend_service,
    list_frontend_services,
)
from ...utils.requests_decorators import cancellable_request
from ...utils.pools import non_blocking_process_pool_executor
from ..dependencies.database import get_repository
from ..dependencies.director import DirectorApi, get_director_api

router = APIRouter()
logger = logging.getLogger(__name__)

ServicesSelection = Set[Tuple[str, str]]

# These are equivalent to pydantic export models but for responses
# SEE https://pydantic-docs.helpmanual.io/usage/exporting_models/#modeldict
# SEE https://fastapi.tiangolo.com/tutorial/response-model/#use-the-response_model_exclude_unset-parameter
RESPONSE_MODEL_POLICY = {
    "response_model_by_alias": True,
    "response_model_exclude_unset": True,
    "response_model_exclude_defaults": False,
    "response_model_exclude_none": False,
}


def _prepare_service_details(
    service_in_registry: Dict[str, Any],
    service_in_db: ServiceMetaDataAtDB,
    service_access_rights_in_db: List[ServiceAccessRightsAtDB],
    service_owner: Optional[str],
) -> Optional[ServiceOut]:
    # compose service from registry and DB
    composed_service = service_in_registry
    composed_service.update(
        service_in_db.dict(exclude_unset=True, exclude={"owner"}),
        access_rights={rights.gid: rights for rights in service_access_rights_in_db},
        owner=service_owner if service_owner else None,
    )

    # validate the service
    validated_service = None
    try:
        validated_service = ServiceOut(**composed_service)
    except ValidationError as exc:
        logger.warning(
            "could not validate service [%s:%s]: %s",
            composed_service.get("key"),
            composed_service.get("version"),
            exc,
        )
    return validated_service


@router.get("", response_model=List[ServiceOut], **RESPONSE_MODEL_POLICY)
@cancellable_request
async def list_services(
    request: Request,  # pylint:disable=unused-argument
    user_id: PositiveInt,
    details: Optional[bool] = True,
    director_client: DirectorApi = Depends(get_director_api),
    groups_repository: GroupsRepository = Depends(get_repository(GroupsRepository)),
    services_repo: ServicesRepository = Depends(get_repository(ServicesRepository)),
    x_simcore_products_name: str = Header(...),
):
    # Access layer
    user_groups = await groups_repository.list_user_groups(user_id)
    if not user_groups:
        # deny access
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You have unsufficient rights to access the services",
        )

    # now get the executable or writable services
    services_in_db = {
        (s.key, s.version): s
        for s in await services_repo.list_services(
            gids=[group.gid for group in user_groups],
            execute_access=True,
            write_access=True,
            combine_access_with_and=False,
            product_name=x_simcore_products_name,
        )
    }

    # Non-detailed views from the services_repo database
    if not details:
        # only return a stripped down version
        # FIXME: add name, ddescription, type, etc...
        services_overview = [
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
            for key, version in services_in_db
        ]
        return services_overview

    # let's get all the services access rights
    get_services_access_rights_task = services_repo.list_services_access_rights(
        key_versions=list(services_in_db.keys()), product_name=x_simcore_products_name
    )

    # let's get the service owners
    get_services_owner_emails_task = groups_repository.list_user_emails_from_gids(
        {s.owner for s in services_in_db.values() if s.owner}
    )

    # getting services from director
    get_registry_services_task = director_client.get("/services")

    (
        services_in_registry,
        services_access_rights,
        services_owner_emails,
    ) = await asyncio.gather(
        get_registry_services_task,
        get_services_access_rights_task,
        get_services_owner_emails_task,
    )

    # NOTE: for the details of the services:
    # 1. we get all the services from the director-v0 (TODO: move the registry to the catalog)
    # 2. we filter the services using the visible ones from the db
    # 3. then we compose the final service using as a base the registry service, overriding with the same
    #    service from the database, adding also the access rights and the owner as email address instead of gid
    # NOTE: this final step runs in a process pool so that it runs asynchronously and does not block in any way
    with non_blocking_process_pool_executor(max_workers=2) as pool:
        services_details = await asyncio.gather(
            *[
                asyncio.get_event_loop().run_in_executor(
                    pool,
                    _prepare_service_details,
                    s,
                    services_in_db[s["key"], s["version"]],
                    services_access_rights[s["key"], s["version"]],
                    services_owner_emails.get(
                        services_in_db[s["key"], s["version"]].owner
                    ),
                )
                for s in list_frontend_services() + services_in_registry
                if (s.get("key"), s.get("version")) in services_in_db
            ]
        )
        return [s for s in services_details if s is not None]


@router.get(
    "/{service_key:path}/{service_version}",
    response_model=ServiceOut,
    **RESPONSE_MODEL_POLICY,
)
async def get_service(
    user_id: int,
    service_key: constr(regex=KEY_RE),
    service_version: constr(regex=VERSION_RE),
    director_client: DirectorApi = Depends(get_director_api),
    groups_repository: GroupsRepository = Depends(get_repository(GroupsRepository)),
    services_repo: ServicesRepository = Depends(get_repository(ServicesRepository)),
    x_simcore_products_name: str = Header(None),
):
    # check the service exists (raise HTTP_404_NOT_FOUND)
    if is_frontend_service(service_key):
        frontend_service: Dict[str, Any] = get_frontend_service(
            key=service_key, version=service_version
        )
        _service_data = frontend_service
    else:
        services_in_registry = await director_client.get(
            f"/services/{urllib.parse.quote_plus(service_key)}/{service_version}"
        )
        _service_data = services_in_registry[0]

    service: ServiceOut = ServiceOut.parse_obj(_service_data)

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


@router.patch(
    "/{service_key:path}/{service_version}",
    response_model=ServiceOut,
    **RESPONSE_MODEL_POLICY,
)
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
    if is_frontend_service(service_key):
        # NOTE: this is a temporary decision after discussing with OM
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot update front-end services",
        )

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
