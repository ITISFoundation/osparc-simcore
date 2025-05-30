"""Services Access Rights policies"""

import logging
import operator
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any, TypedDict, cast

import arrow
from fastapi import FastAPI
from models_library.groups import GroupID
from models_library.products import ProductName
from models_library.services import ServiceMetaDataPublished
from models_library.services_types import ServiceKey, ServiceVersion
from packaging.version import Version
from pydantic.types import PositiveInt
from sqlalchemy.ext.asyncio import AsyncEngine

from ..api._dependencies.director import get_director_client
from ..models.services_db import ServiceAccessRightsDB, ServiceMetaDataDBGet
from ..repository.groups import GroupsRepository
from ..repository.services import ServicesRepository
from ..utils.versioning import as_version, is_patch_release

_logger = logging.getLogger(__name__)

_LEGACY_SERVICES_DATE: datetime = datetime(year=2020, month=8, day=19, tzinfo=UTC)


class InheritedData(TypedDict):
    access_rights: list[ServiceAccessRightsDB]
    metadata_updates: dict[str, Any]


def _is_frontend_service(service: ServiceMetaDataPublished) -> bool:
    return "/frontend/" in service.key


async def _is_old_service(app: FastAPI, service: ServiceMetaDataPublished) -> bool:
    # NOTE: https://github.com/ITISFoundation/osparc-simcore/pull/6003#discussion_r1658200909
    # get service build date
    client = get_director_client(app)

    data = await client.get_service_extras(service.key, service.version)
    if not data or data.service_build_details is None:
        return True
    service_build_data = arrow.get(data.service_build_details.build_date).datetime
    return bool(service_build_data < _LEGACY_SERVICES_DATE)


async def evaluate_default_service_ownership_and_rights(
    app: FastAPI, *, service: ServiceMetaDataPublished, product_name: ProductName
) -> tuple[GroupID | None, list[ServiceAccessRightsDB]]:
    """Evaluates the owner (group_id) and the access rights for a service

    This function determines:
    1. Who owns the service (based on contact or author email)
    2. Who can access the service based on the following rules:
       - All services published before August 19, 2020 (_LEGACY_SERVICES_DATE) are accessible to everyone
       - Services published after August 19, 2020 are only accessible to their owner
       - Frontend services are accessible to everyone regardless of publication date

    Args:
        app: FastAPI application instance containing database engine and settings
        service: Service metadata including key, version, contact and authors information

    Returns:
        A tuple containing:
        - The owner's group ID (gid) if found, None otherwise
        - A list of ServiceAccessRightsDB objects representing the default access rights
          for the service, including who can execute and/or modify the service

    Raises:
        HTTPException: If there's an error communicating with the director API
        SQLAlchemyError: If there's an error accessing the database
        ValidationError: If there's an error validating the Pydantic models
    """
    db_engine: AsyncEngine = app.state.engine

    groups_repo = GroupsRepository(db_engine)
    owner_gid = None
    group_ids: list[PositiveInt] = []

    # 1. If service is old or frontend, we add the everyone group
    if _is_frontend_service(service) or await _is_old_service(app, service):
        everyone_gid = (await groups_repo.get_everyone_group()).gid
        group_ids.append(everyone_gid)  # let's make that one available to everyone
        _logger.debug(
            "service %s:%s is old or frontend. Set available to everyone",
            service.key,
            service.version,
        )

    # 2. Deducing the owner gid
    possible_owner_email = [service.contact] + [
        author.email for author in service.authors
    ]

    for user_email in possible_owner_email:
        possible_gid = await groups_repo.get_user_gid_from_email(user_email)
        if possible_gid and not owner_gid:
            owner_gid = possible_gid
    if not owner_gid:
        _logger.warning("Service %s:%s has no owner", service.key, service.version)
    else:
        group_ids.append(owner_gid)

    # 3. Aplying default access rights
    default_access_rights = [
        ServiceAccessRightsDB(
            key=service.key,
            version=service.version,
            gid=gid,
            execute_access=True,
            write_access=(
                gid == owner_gid
            ),  # we add the owner with full rights, unless it's everyone
            product_name=product_name,
        )
        for gid in set(group_ids)
    ]

    return (owner_gid, default_access_rights)


async def _find_previous_compatible_release(
    services_repo: ServicesRepository, *, service_metadata: ServiceMetaDataPublished
) -> ServiceMetaDataDBGet | None:
    """
    Finds the previous compatible release for a service.

    Args:
        services_repo: Instance of ServicesRepository for database access.
        service_metadata: Metadata of the service being evaluated.

    Returns:
        The previous compatible release if found, None otherwise.
    """
    if _is_frontend_service(service_metadata):
        return None

    new_version: Version = as_version(service_metadata.version)
    latest_releases = await services_repo.list_service_releases(
        service_metadata.key,
        major=new_version.major,
        minor=new_version.minor,
        limit_count=5,
    )

    # FIXME: deprecated versions hsould not coutn!!!

    # latest_releases is sorted from newer to older
    for release in latest_releases:
        # COMPATIBILITY RULE:
        # - a patch release is compatible with the previous patch release

        # FIXME: not all compatible releases!!!
        if is_patch_release(new_version, release.version):
            return release

    return None


async def inherit_from_latest_compatible_release(
    services_repo: ServicesRepository, *, service_metadata: ServiceMetaDataPublished
) -> InheritedData:
    """
    Inherits metadata and access rights from a previous compatible release.

    This function applies inheritance policies:
    - AUTO-UPGRADE PATCH policy: new patch releases inherit access rights from previous compatible versions
    - Metadata inheritance: icon and other metadata fields are inherited if not specified in the new version

    Args:
        services_repo: Instance of ServicesRepository for database access.
        service_metadata: Metadata of the service being evaluated.

    Returns:
        An InheritedData object containing:
        - access_rights: List of ServiceAccessRightsDB objects inherited from the previous release
        - metadata_updates: Dict of metadata fields that should be updated in the new service

    Notes:
        - The policy is described in https://github.com/ITISFoundation/osparc-simcore/issues/2244
        - Inheritance is only for patch releases (i.e., same major and minor version).
    """
    inherited_data: InheritedData = {
        "access_rights": [],
        "metadata_updates": {},
    }

    previous_release = await _find_previous_compatible_release(
        services_repo, service_metadata=service_metadata
    )

    if not previous_release:
        return inherited_data

    # 1. ACCESS-RIGHTS:
    #    Inherit access rights (from all products) from the previous release
    previous_access_rights = await services_repo.get_service_access_rights(
        previous_release.key, previous_release.version
    )

    inherited_data["access_rights"] = [
        access.model_copy(
            update={"version": service_metadata.version},
            deep=True,
        )
        for access in previous_access_rights
    ]

    # 2. METADATA:
    #    Inherit icon if not specified in the new service
    if not service_metadata.icon and previous_release.icon:
        inherited_data["metadata_updates"]["icon"] = previous_release.icon

    return inherited_data


def reduce_access_rights(
    access_rights: list[ServiceAccessRightsDB],
    reduce_operation: Callable = operator.ior,
) -> list[ServiceAccessRightsDB]:
    """Reduces a list of access-rights per target

    By default, the reduction is OR (i.e. preserves True flags)

    """
    # TODO: probably a lot of room to optimize
    # helper functions to simplify operation of access rights

    def _get_target(access: ServiceAccessRightsDB) -> tuple[str | int, ...]:
        """Hashable identifier of the resource the access rights apply to"""
        return (access.key, access.version, access.gid, access.product_name)

    def _get_flags(access: ServiceAccessRightsDB) -> dict[str, bool]:
        """Extracts only"""
        flags = access.model_dump(include={"execute_access", "write_access"})
        return cast(dict[str, bool], flags)

    access_flags_map: dict[tuple[str | int, ...], dict[str, bool]] = {}
    for access in access_rights:
        target = _get_target(access)
        access_flags = access_flags_map.get(target)

        if access_flags:
            # applies reduction on flags
            for key, value in _get_flags(access).items():
                access_flags[key] = reduce_operation(  # defaults to a |= b
                    access_flags[key], value
                )
        else:
            access_flags_map[target] = _get_flags(access)

    reduced_access_rights: list[ServiceAccessRightsDB] = [
        ServiceAccessRightsDB(
            key=ServiceKey(f"{target[0]}"),
            version=ServiceVersion(f"{target[1]}"),
            gid=int(target[2]),
            product_name=f"{target[3]}",
            **access_flags_map[target],
        )
        for target in access_flags_map
    ]

    return reduced_access_rights
