"""Services Access Rights policies"""

import logging
import operator
from collections.abc import Callable
from datetime import UTC, datetime
from typing import cast

import arrow
from fastapi import FastAPI
from models_library.services import ServiceMetaDataPublished
from models_library.services_types import ServiceKey, ServiceVersion
from packaging.version import Version
from pydantic.types import PositiveInt
from sqlalchemy.ext.asyncio import AsyncEngine

from ..api._dependencies.director import get_director_client
from ..models.services_db import ServiceAccessRightsDB
from ..repository.groups import GroupsRepository
from ..repository.services import ServicesRepository
from ..utils.versioning import as_version, is_patch_release

_logger = logging.getLogger(__name__)

_LEGACY_SERVICES_DATE: datetime = datetime(year=2020, month=8, day=19, tzinfo=UTC)


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


async def evaluate_default_policy(
    app: FastAPI, service: ServiceMetaDataPublished
) -> tuple[PositiveInt | None, list[ServiceAccessRightsDB]]:
    """Given a service, it returns the owner's group-id (gid) and a list of access rights following
    default access-rights policies

    - DEFAULT Access Rights policies:
        1. All services published in osparc prior 19.08.2020 will be visible to everyone (refered as 'old service').
        2. Services published after 19.08.2020 will be visible ONLY to his/her owner
        3. Front-end services are have execute-access to everyone

    Raises:
        HTTPException: from calls to director's rest API. Maps director errors into catalog's server error
        SQLAlchemyError: from access to pg database
        ValidationError: from pydantic model errors
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
        _logger.warning("service %s:%s has no owner", service.key, service.version)
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
            product_name=app.state.default_product_name,
        )
        for gid in set(group_ids)
    ]

    return (owner_gid, default_access_rights)


async def evaluate_auto_upgrade_policy(
    service_metadata: ServiceMetaDataPublished, services_repo: ServicesRepository
) -> list[ServiceAccessRightsDB]:
    # AUTO-UPGRADE PATCH policy:
    #
    #  - Any new patch released, inherits the access rights from previous compatible version
    #  - IDEA: add as option in the publication contract, i.e. in ServiceDockerData?
    #  - Does NOT apply to front-end services
    #
    # SEE https://github.com/ITISFoundation/osparc-simcore/issues/2244)
    #
    if _is_frontend_service(service_metadata):
        return []

    service_access_rights = []
    new_version: Version = as_version(service_metadata.version)
    latest_releases = await services_repo.list_service_releases(
        service_metadata.key,
        major=new_version.major,
        minor=new_version.minor,
    )

    previous_release = None
    for release in latest_releases:
        # NOTE: latest_release is sorted from newer to older
        # Here we search for the previous version patched by new-version
        if is_patch_release(new_version, release.version):
            previous_release = release
            break

    if previous_release:
        previous_access_rights = await services_repo.get_service_access_rights(
            previous_release.key, previous_release.version
        )

        service_access_rights = [
            access.model_copy(
                update={"version": service_metadata.version},
                deep=True,
            )
            for access in previous_access_rights
        ]
    return service_access_rights


def reduce_access_rights(
    access_rights: list[ServiceAccessRightsDB],
    reduce_operation: Callable = operator.ior,
) -> list[ServiceAccessRightsDB]:
    """
    Reduces a list of access-rights per target
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
