""" Services Access Rights policies

"""
from typing import List

from models_library.services import ServiceAccessRightsAtDB, ServiceDockerData
from packaging.version import Version

from ..db.repositories.services import ServicesRepository
from ..utils.versioning import as_version, is_patch_release


async def evaluate_auto_upgrade_policy(
    service_metadata: ServiceDockerData, services_repo: ServicesRepository
):
    # AUTO-UPGRADE PATCH policy:
    #
    #  - Any new patch released, inherits the access rights from previous compatible version
    #  - TODO: add as option in the publication contract, i.e. in ServiceDockerData
    #  - Does NOT apply to front-end services
    #
    # SEE https://github.com/ITISFoundation/osparc-simcore/issues/2244)
    #
    if "/frontend/" in service_metadata.key:
        return []

    service_access_rights = []
    version: Version = as_version(service_metadata.version)
    latest_releases = await services_repo.list_service_releases(
        service_metadata.key, major=version.major, minor=version.minor, limit_count=1
    )
    assert len(latest_releases) <= 1  # nosec

    if latest_releases:
        latest_patch = latest_releases[0]

        if is_patch_release(latest_patch.version, version):
            previous_access_rights = await services_repo.get_service_access_rights(
                latest_patch.key, latest_patch.version
            )
            for access in previous_access_rights:
                service_access_rights.append(
                    access.copy(
                        exclude={"created", "modified"},
                        update={"version": service_metadata.version},
                    )
                )

    return service_access_rights


def merge_access_rights(
    access_rights: List[ServiceAccessRightsAtDB],
) -> List[ServiceAccessRightsAtDB]:
    # TODO: probably a lot of room to optimize
    merged = {}
    for access in access_rights:
        resource = access.get_resource()
        flags = merged.get(resource)
        if flags:
            for key, value in access.get_flags().items():
                flags[key] |= value
        else:
            merged[resource] = access.get_flags()

    merged_access_rights = []
    for resource in merged:
        merged_access_rights.append(
            ServiceAccessRightsAtDB.create_from(resource, merged[resource])
        )

    return merged_access_rights
