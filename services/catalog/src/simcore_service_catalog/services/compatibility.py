""" Manages service compatibility policies

"""

from models_library.basic_types import VersionStr
from models_library.products import ProductName
from models_library.services_base import ServiceKeyVersion
from models_library.services_history import Compatibility
from models_library.services_types import ServiceKey, ServiceVersion
from models_library.users import UserID
from packaging.specifiers import SpecifierSet
from packaging.version import Version
from simcore_postgres_database.models.services_compatibility import CompatiblePolicyDict
from simcore_service_catalog.utils.versioning import as_version

from ..db.repositories.services import ServicesRepository
from ..models.services_db import ReleaseFromDB


def _get_default_compatibility_specs(target: ServiceVersion | Version) -> SpecifierSet:
    """Default policy:

    A version is compatible with target X.Y.Z iff `>X.Y.Z, ~=X.Y.Z`

    SEE https://packaging.python.org/en/latest/specifications/version-specifiers/#id5
    """
    version = as_version(target)

    newer_version_spec = SpecifierSet(f">{version}")
    patch_compatible_spec = SpecifierSet(
        f"~={version.major}.{version.minor}.{version.micro}"
    )
    return newer_version_spec & patch_compatible_spec


def _get_latest_compatible_version(
    target: ServiceVersion | Version,
    service_versions: list[Version],
    compatibility_specs: SpecifierSet | None = None,
) -> Version | None:
    """
    Returns latest version in history that satisfies `>X.Y.Z, ~=X.Y.Z` (default policy if compatibility_specs=None) or compatibility_specs
    Returns None if no version in history satisfies specs.
    """

    compatibility_specs = compatibility_specs or _get_default_compatibility_specs(
        target
    )
    try:
        return max(compatibility_specs.filter(service_versions))
    except ValueError:  # no matches
        return None


def _to_versions(service_history: list[ReleaseFromDB]) -> list[Version]:
    return sorted(
        (as_version(h.version) for h in service_history if not h.deprecated),
        reverse=True,  # latest first
    )


async def _eval_custom_compatibility(
    repo: ServicesRepository,
    product_name: ProductName,
    user_id: UserID,
    compatibility_policy: CompatiblePolicyDict,
    target_version: ServiceVersion,
    service_versions: list[Version],
) -> Compatibility | None:
    # TODO: guarantees on these data structures!
    versions_specifier = SpecifierSet(compatibility_policy["versions_specifier"])

    other_service_key = compatibility_policy.get("other_service_key")
    other_service_versions = None

    if other_service_key and (
        other_service := await repo.get_service_with_history(
            product_name=product_name,
            user_id=user_id,
            key=ServiceKey(other_service_key),
            version=None,  # TODO: get_service_history(service_key)
        )
    ):
        other_service_versions = _to_versions(other_service.history)

    if version := _get_latest_compatible_version(
        target_version,
        other_service_versions or service_versions,
        versions_specifier,  # custom policy
    ):
        if other_service_key:
            return Compatibility(
                can_update_to=ServiceKeyVersion(
                    key=other_service_key, version=VersionStr(version)
                )
            )
        return Compatibility(can_update_to=ServiceKey(f"{version}"))
    return None


async def eval_service_compatibility(
    repo: ServicesRepository,
    product_name: ProductName,
    user_id: UserID,
    service_history: list[ReleaseFromDB],
) -> dict[ServiceVersion, Compatibility]:

    latest_first_versions = _to_versions(service_history)

    result = {}
    for release in service_history:
        compatibility = None

        # custom compatibility policy
        if release.compatibility_policy:
            compatibility = await _eval_custom_compatibility(
                product_name=product_name,
                user_id=user_id,
                repo=repo,
                target_version=release.version,
                compatibility_policy=release.compatibility_policy,
                service_versions=latest_first_versions,
            )

        elif version := _get_latest_compatible_version(
            release.version,
            latest_first_versions,
            None,  # default policy
        ):
            compatibility = Compatibility(can_update_to=ServiceKey(f"{version}"))

        result[release.version] = compatibility

    return result
