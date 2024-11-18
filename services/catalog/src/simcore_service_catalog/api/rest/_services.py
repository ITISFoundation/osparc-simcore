# pylint: disable=too-many-arguments

import asyncio
import logging
import urllib.parse
from typing import Annotated, Any, TypeAlias, cast

from aiocache import cached  # type: ignore[import-untyped]
from fastapi import APIRouter, Depends, Header, HTTPException, status
from models_library.api_schemas_catalog.services import ServiceGet, ServiceUpdate
from models_library.services import ServiceKey, ServiceType, ServiceVersion
from models_library.services_metadata_published import ServiceMetaDataPublished
from pydantic import ValidationError
from pydantic.types import PositiveInt
from servicelib.fastapi.requests_decorators import cancel_on_disconnect
from starlette.requests import Request

from ..._constants import (
    DIRECTOR_CACHING_TTL,
    LIST_SERVICES_CACHING_TTL,
    RESPONSE_MODEL_POLICY,
)
from ...db.repositories.groups import GroupsRepository
from ...db.repositories.services import ServicesRepository
from ...models.services_db import ServiceAccessRightsAtDB, ServiceMetaDataAtDB
from ...services.director import DirectorApi
from ...services.function_services import is_function_service
from ..dependencies.database import get_repository
from ..dependencies.director import get_director_api
from ..dependencies.services import get_service_from_manifest

_logger = logging.getLogger(__name__)

ServicesSelection: TypeAlias = set[tuple[str, str]]


def _compose_service_details(
    service_in_registry: dict[str, Any],  # published part
    service_in_db: ServiceMetaDataAtDB,  # editable part
    service_access_rights_in_db: list[ServiceAccessRightsAtDB],
    service_owner: str | None,
) -> ServiceGet | None:
    # compose service from registry and DB
    service = service_in_registry
    service.update(
        service_in_db.model_dump(exclude_unset=True, exclude={"owner"}),
        access_rights={rights.gid: rights for rights in service_access_rights_in_db},
        owner=service_owner if service_owner else None,
    )

    # validate the service
    try:
        return ServiceGet(**service)
    except ValidationError as exc:
        _logger.warning(
            "Could not validate service [%s:%s]: %s",
            service.get("key"),
            service.get("version"),
            exc,
        )
    return None


def _build_cache_key(fct, *_, **kwargs):
    return f"{fct.__name__}_{kwargs['user_id']}_{kwargs['x_simcore_products_name']}_{kwargs['details']}"


#
# Routes
#

router = APIRouter()


# NOTE: this call is pretty expensive and can be called several times
# (when e2e runs or by the webserver when listing projects) therefore
# a cache is setup here
@router.get("", response_model=list[ServiceGet], **RESPONSE_MODEL_POLICY)
@cancel_on_disconnect
@cached(
    ttl=LIST_SERVICES_CACHING_TTL,
    key_builder=_build_cache_key,
)
async def list_services(
    request: Request,  # pylint:disable=unused-argument
    *,
    user_id: PositiveInt,
    director_client: Annotated[DirectorApi, Depends(get_director_api)],
    groups_repository: Annotated[
        GroupsRepository, Depends(get_repository(GroupsRepository))
    ],
    services_repo: Annotated[
        ServicesRepository, Depends(get_repository(ServicesRepository))
    ],
    x_simcore_products_name: Annotated[str, Header(...)],
    details: bool = True,
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
        # NOTE: here validation is not necessary since key,version were already validated
        # in terms of time, this takes the most
        return [
            ServiceGet.model_construct(
                key=key,
                version=version,
                name="nodetails",
                description="nodetails",
                type=ServiceType.COMPUTATIONAL,
                authors=[{"name": "nodetails", "email": "nodetails@nodetails.com"}],
                contact="nodetails@nodetails.com",
                inputs={},
                outputs={},
                deprecated=services_in_db[(key, version)].deprecated,
                classifiers=[],
                owner=None,
            )
            for key, version in services_in_db
        ]

    # caching this steps brings down the time to generate it at the expense of being sometimes a bit out of date
    @cached(ttl=DIRECTOR_CACHING_TTL)
    async def cached_registry_services() -> dict[str, Any]:
        return cast(dict[str, Any], await director_client.get("/services"))

    (
        services_in_registry,
        services_access_rights,
        services_owner_emails,
    ) = await asyncio.gather(
        cached_registry_services(),
        services_repo.list_services_access_rights(
            key_versions=services_in_db,
            product_name=x_simcore_products_name,
        ),
        groups_repository.list_user_emails_from_gids(
            {s.owner for s in services_in_db.values() if s.owner}
        ),
    )

    # NOTE: for the details of the services:
    # 1. we get all the services from the director-v0 (TODO: move the registry to the catalog)
    # 2. we filter the services using the visible ones from the db
    # 3. then we compose the final service using as a base the registry service, overriding with the same
    #    service from the database, adding also the access rights and the owner as email address instead of gid
    # NOTE: This step takes the bulk of the time to generate the list
    services_details = await asyncio.gather(
        *[
            asyncio.get_event_loop().run_in_executor(
                None,
                _compose_service_details,
                s,
                services_in_db[s["key"], s["version"]],
                services_access_rights[s["key"], s["version"]],
                services_owner_emails.get(
                    services_in_db[s["key"], s["version"]].owner or 0
                ),
            )
            for s in (
                request.app.state.frontend_services_catalog + services_in_registry
            )
            if (s.get("key"), s.get("version")) in services_in_db
        ]
    )
    return [s for s in services_details if s is not None]


@router.get(
    "/{service_key:path}/{service_version}",
    response_model=ServiceGet,
    **RESPONSE_MODEL_POLICY,
)
async def get_service(
    user_id: int,
    service_in_manifest: Annotated[
        ServiceMetaDataPublished, Depends(get_service_from_manifest)
    ],
    groups_repository: Annotated[
        GroupsRepository, Depends(get_repository(GroupsRepository))
    ],
    services_repo: Annotated[
        ServicesRepository, Depends(get_repository(ServicesRepository))
    ],
    x_simcore_products_name: str = Header(None),
):
    service_data: dict[str, Any] = {"owner": None}

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
        service_in_manifest.key,
        service_in_manifest.version,
        gids=[group.gid for group in user_groups],
        write_access=True,
        product_name=x_simcore_products_name,
    )
    if service_in_db:
        # we have full access, let's add the access to the output
        service_access_rights: list[
            ServiceAccessRightsAtDB
        ] = await services_repo.get_service_access_rights(
            service_in_manifest.key,
            service_in_manifest.version,
            product_name=x_simcore_products_name,
        )
        service_data["access_rights"] = {
            rights.gid: rights for rights in service_access_rights
        }
    else:
        # check if we have executable rights
        service_in_db = await services_repo.get_service(
            service_in_manifest.key,
            service_in_manifest.version,
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

    # the owner shall be converted to an email address
    if service_in_db.owner:
        service_data["owner"] = await groups_repository.get_user_email_from_gid(
            service_in_db.owner
        )

    # access is allowed, override some of the values with what is in the db
    service_data.update(
        service_in_manifest.model_dump(exclude_unset=True, by_alias=True)
        | service_in_db.model_dump(exclude_unset=True, exclude={"owner"})
    )
    return service_data


@router.patch(
    "/{service_key:path}/{service_version}",
    response_model=ServiceGet,
    **RESPONSE_MODEL_POLICY,
)
async def update_service(
    # pylint: disable=too-many-arguments
    user_id: int,
    service_key: ServiceKey,
    service_version: ServiceVersion,
    updated_service: ServiceUpdate,
    director_client: Annotated[DirectorApi, Depends(get_director_api)],
    groups_repository: Annotated[
        GroupsRepository, Depends(get_repository(GroupsRepository))
    ],
    services_repo: Annotated[
        ServicesRepository, Depends(get_repository(ServicesRepository))
    ],
    x_simcore_products_name: Annotated[str | None, Header()] = None,
):
    if is_function_service(service_key):
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
            **updated_service.model_dump(exclude_unset=True),
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
        assert x_simcore_products_name  # nosec
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
    assert x_simcore_products_name  # nosec
    return await get_service(
        user_id=user_id,
        service_in_manifest=await get_service_from_manifest(
            service_key, service_version, director_client
        ),
        groups_repository=groups_repository,
        services_repo=services_repo,
        x_simcore_products_name=x_simcore_products_name,
    )
