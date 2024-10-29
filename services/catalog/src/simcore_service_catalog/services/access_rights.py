""" Services Access Rights policies

"""

import logging
import operator
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any, cast
from urllib.parse import quote_plus

import arrow
from fastapi import FastAPI
from models_library.services import ServiceMetaDataPublished
from models_library.services_types import ServiceKey, ServiceVersion
from packaging.version import Version
from pydantic.types import PositiveInt
from sqlalchemy.ext.asyncio import AsyncEngine

from ..api.dependencies.director import get_director_api
from ..db.repositories.groups import GroupsRepository
from ..db.repositories.services import ServicesRepository
from ..models.services_db import ServiceAccessRightsAtDB
from ..utils.versioning import as_version, is_patch_release

_logger = logging.getLogger(__name__)

_LEGACY_SERVICES_DATE: datetime = datetime(year=2020, month=8, day=19, tzinfo=UTC)


def _is_frontend_service(service: ServiceMetaDataPublished) -> bool:
    return "/frontend/" in service.key


async def _is_old_service(app: FastAPI, service: ServiceMetaDataPublished) -> bool:
    # NOTE: https://github.com/ITISFoundation/osparc-simcore/pull/6003#discussion_r1658200909
    # get service build date
    client = get_director_api(app)
    data = cast(
        dict[str, Any],
        await client.get(
            f"/service_extras/{quote_plus(service.key)}/{service.version}"
        ),
    )
    if not data or "build_date" not in data:
        return True
    service_build_data = arrow.get(data["build_date"]).datetime
    return bool(service_build_data < _LEGACY_SERVICES_DATE)


async def evaluate_default_policy(
    app: FastAPI, service: ServiceMetaDataPublished
) -> tuple[PositiveInt | None, list[ServiceAccessRightsAtDB]]:
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

    if _is_frontend_service(service) or await _is_old_service(app, service):
        everyone_gid = (await groups_repo.get_everyone_group()).gid
        _logger.debug("service %s:%s is old or frontend", service.key, service.version)
        # let's make that one available to everyone
        group_ids.append(everyone_gid)

    # try to find the owner
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

    # we add the owner with full rights, unless it's everyone
    default_access_rights = [
        ServiceAccessRightsAtDB(
            key=service.key,
            version=service.version,
            gid=gid,
            execute_access=True,
            write_access=(gid == owner_gid),
            product_name=app.state.default_product_name,
        )
        for gid in set(group_ids)
    ]

    return (owner_gid, default_access_rights)


async def evaluate_auto_upgrade_policy(
    service_metadata: ServiceMetaDataPublished, services_repo: ServicesRepository
) -> list[ServiceAccessRightsAtDB]:
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
    access_rights: list[ServiceAccessRightsAtDB],
    reduce_operation: Callable = operator.ior,
) -> list[ServiceAccessRightsAtDB]:
    """
    Reduces a list of access-rights per target
    By default, the reduction is OR (i.e. preserves True flags)
    """
    # TODO: probably a lot of room to optimize
    # helper functions to simplify operation of access rights

    def _get_target(access: ServiceAccessRightsAtDB) -> tuple[str | int, ...]:
        """Hashable identifier of the resource the access rights apply to"""
        return (access.key, access.version, access.gid, access.product_name)

    def _get_flags(access: ServiceAccessRightsAtDB) -> dict[str, bool]:
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
                access_flags[key] = reduce_operation(access_flags[key], value)  # a |= b
        else:
            access_flags_map[target] = _get_flags(access)

    reduced_access_rights: list[ServiceAccessRightsAtDB] = [
        ServiceAccessRightsAtDB(
            key=ServiceKey(f"{target[0]}"),
            version=ServiceVersion(f"{target[1]}"),
            gid=int(target[2]),
            product_name=f"{target[3]}",
            **access_flags_map[target],
        )
        for target in access_flags_map
    ]

    return reduced_access_rights
