""" Services Access Rights policies

"""
import logging
from datetime import datetime
from typing import List, Optional, Tuple
from urllib.parse import quote_plus

from aiopg.sa.engine import Engine
from fastapi import FastAPI
from models_library.services import ServiceAccessRightsAtDB, ServiceDockerData
from packaging.version import Version
from pydantic.types import PositiveInt

from ..api.dependencies.director import get_director_api
from ..db.repositories.groups import GroupsRepository
from ..db.repositories.services import ServicesRepository
from ..utils.versioning import as_version, is_patch_release

logger = logging.getLogger(__name__)

OLD_SERVICES_DATE: datetime = datetime(2020, 8, 19)


def _is_frontend_service(service: ServiceDockerData) -> bool:
    return "/frontend/" in service.key


async def _is_old_service(app: FastAPI, service: ServiceDockerData) -> bool:
    # get service build date
    client = get_director_api(app)
    data = await client.get(
        f"/service_extras/{quote_plus(service.key)}/{service.version}"
    )
    if not data or "build_date" not in data:
        return True

    logger.debug("retrieved service extras are %s", data)

    service_build_data = datetime.strptime(data["build_date"], "%Y-%m-%dT%H:%M:%SZ")
    return service_build_data < OLD_SERVICES_DATE


async def evaluate_default_policy(
    app: FastAPI, service: ServiceDockerData
) -> Tuple[Optional[PositiveInt], List[ServiceAccessRightsAtDB]]:
    """Given a service, it returns the owner's group-id (gid) and a list of access rights following
    default access-rights policies

    - DEFAULT Access Rights policies:
        1. All services published in osparc prior 19.08.2020 will be visible to everyone (refered as 'old service').
        2. Services published after 19.08.2020 will be visible ONLY to his/her owner
        3. Front-end services are have read-access to everyone
    """
    db_engine: Engine = app.state.engine

    groups_repo = GroupsRepository(db_engine)

    everyone_gid = (await groups_repo.get_everyone_group()).gid
    owner_gid = None
    reader_gids: List[PositiveInt] = []

    if _is_frontend_service(service) or await _is_old_service(app, service):
        logger.debug("service %s:%s is old or frontend", service.key, service.version)
        # let's make that one available to everyone
        reader_gids.append(everyone_gid)

    # try to find the owner
    possible_owner_email = [service.contact] + [
        author.email for author in service.authors
    ]

    for user_email in possible_owner_email:
        possible_gid = await groups_repo.get_user_gid_from_email(user_email)
        if possible_gid:
            if not owner_gid:
                owner_gid = possible_gid
    if not owner_gid:
        logger.warning("service %s:%s has no owner", service.key, service.version)
    else:
        reader_gids.append(owner_gid)

    # we add the owner with full rights, unless it's everyone
    default_access_rights = [
        ServiceAccessRightsAtDB(
            key=service.key,
            version=service.version,
            gid=gid,
            execute_access=True,
            write_access=(gid == owner_gid),
            product_name=app.state.settings.access_rights_default_product_name,
        )
        for gid in set(reader_gids)
    ]

    # Patch releases inherit access rights from previous version

    return (owner_gid, default_access_rights)


async def evaluate_auto_upgrade_policy(
    service_metadata: ServiceDockerData, services_repo: ServicesRepository
) -> List[ServiceAccessRightsAtDB]:
```?
    # AUTO-UPGRADE PATCH policy:
    #
    #  - Any new patch released, inherits the access rights from previous compatible version
    #  - TODO: add as option in the publication contract, i.e. in ServiceDockerData
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
        limit_count=1,
    )
    assert len(latest_releases) <= 1  # nosec

    if latest_releases:
        latest_patch = latest_releases[0]

        if is_patch_release(new_version, latest_patch.version):
            previous_access_rights = await services_repo.get_service_access_rights(
                latest_patch.key, latest_patch.version
            )

            for access in previous_access_rights:
                service_access_rights.append(
                    access.copy(
                        exclude={"created", "modified"},
                        update={"version": service_metadata.version},
                        deep=True,
                    )
                )

    return service_access_rights


def merge_access_rights(
    access_rights: List[ServiceAccessRightsAtDB],
) -> List[ServiceAccessRightsAtDB]:
    # TODO: not generic enought.
    # TODO: probably a lot of room to optimize
    merged = {}
    for access in access_rights:
        resource = access.get_resource()
        flags = merged.get(resource)
        if flags:
            for key, value in access.get_flags().items():
                # WARNING: if accesss is given once, it is maintained!
                flags[key] |= value
        else:
            merged[resource] = access.get_flags()

    merged_access_rights = []
    for resource in merged:
        merged_access_rights.append(
            ServiceAccessRightsAtDB.create_from(resource, merged[resource])
        )

    return merged_access_rights
