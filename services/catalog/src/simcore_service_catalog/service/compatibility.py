"""Manages service compatibility policies"""

from models_library.products import ProductName
from models_library.services_history import Compatibility, CompatibleService
from models_library.services_types import ServiceKey, ServiceVersion
from models_library.users import UserID
from packaging.specifiers import SpecifierSet
from packaging.version import Version

from simcore_service_catalog.utils.versioning import as_version

from ..models.services_db import ReleaseDBGet
from ..repository.services import ServicesRepository


def _get_default_compatibility_specs(target: ServiceVersion | Version) -> SpecifierSet:
    """Default policy:
    A version is compatible with target X.Y.Z if `>X.Y.Z, ~=X.Y.Z` (i.e. any patch released newer than the target)
    SEE https://packaging.python.org/en/latest/specifications/version-specifiers/#id5
    """
    version = as_version(target)
    return SpecifierSet(f">{version}, ~={version.major}.{version.minor}.{version.micro}")


def _get_latest_compatible_version(
    target: ServiceVersion | Version,
    service_versions: list[Version],
    compatibility_specs: SpecifierSet | None = None,
) -> Version | None:
    """
    Returns latest version in history that satisfies `>X.Y.Z, ~=X.Y.Z`
    (default policy if compatibility_specs=None) or compatibility_specs
    Returns None if no version in history satisfies specs.
    """
    compatibility_specs = compatibility_specs or _get_default_compatibility_specs(target)
    compatible_versions = [v for v in service_versions if v in compatibility_specs]
    return max(compatible_versions, default=None)


def _convert_to_versions(service_history: list[ReleaseDBGet]) -> list[Version]:
    return sorted(
        (as_version(h.version) for h in service_history if not h.deprecated),
        reverse=True,  # latest first
    )


def _latest_stable_release_by_minor(
    released_versions: list[Version],
) -> dict[tuple[int, int], Version]:
    """Maps (major, minor) -> latest non-prerelease version in that series.

    `released_versions` MUST be sorted latest-first so the first entry seen per
    series is its maximum. This resolves the default compatibility policy
    (`>X.Y.Z, ~=X.Y.Z`) in O(1) per target instead of scanning all versions
    with a `SpecifierSet`. Prereleases are excluded to match the default
    `SpecifierSet` semantics.
    """
    latest_by_minor: dict[tuple[int, int], Version] = {}
    for version in released_versions:
        if version.is_prerelease:
            continue
        minor_series = (version.major, version.minor)
        if minor_series not in latest_by_minor:
            latest_by_minor[minor_series] = version
    return latest_by_minor


async def _evaluate_custom_compatibility(
    repo: ServicesRepository,
    product_name: ProductName,
    user_id: UserID,
    target_version: ServiceVersion,
    released_versions: list[Version],
    compatibility_policy: dict,
    other_service_history_cache: dict[str, list[ReleaseDBGet]],
) -> Compatibility | None:
    other_service_key = compatibility_policy.get("other_service_key")
    other_service_versions = []

    if other_service_key:
        if other_service_key not in other_service_history_cache:
            other_service_history_cache[other_service_key] = await repo.get_service_history(
                product_name=product_name,
                user_id=user_id,
                key=ServiceKey(other_service_key),
            )
        if other_service_history := other_service_history_cache[other_service_key]:
            other_service_versions = _convert_to_versions(other_service_history)

    versions_specifier = SpecifierSet(compatibility_policy["versions_specifier"])
    versions_to_check = other_service_versions or released_versions

    if latest_version := _get_latest_compatible_version(target_version, versions_to_check, versions_specifier):
        if other_service_key:
            return Compatibility(
                can_update_to=CompatibleService(
                    key=other_service_key,
                    version=f"{latest_version}",
                )
            )
        return Compatibility(
            can_update_to=CompatibleService(
                version=f"{latest_version}",
            )
        )

    return None


def _evaluate_default_compatibility(
    target: Version,
    released_versions: list[Version],
    latest_stable_by_minor: dict[tuple[int, int], Version],
) -> Compatibility | None:
    """Default policy `>X.Y.Z, ~=X.Y.Z`: latest stable patch in the same
    (major, minor) series that is strictly newer than the target.
    """
    if target.is_prerelease:
        # prereleases follow different specifier semantics: use the exact (slow) path
        latest = _get_latest_compatible_version(target, released_versions)
    else:
        latest = latest_stable_by_minor.get((target.major, target.minor))
        if latest is not None and latest <= target:
            latest = None

    if latest is not None:
        return Compatibility(can_update_to=CompatibleService(version=f"{latest}"))
    return None


async def evaluate_service_compatibility_map(
    repo: ServicesRepository,
    product_name: ProductName,
    user_id: UserID,
    service_release_history: list[ReleaseDBGet],
) -> dict[ServiceVersion, Compatibility | None]:
    """
    Evaluates the compatibility among a list of service releases for a given product and user.

    """
    compatibility_map: dict[ServiceVersion, Compatibility | None] = {}

    released_versions = _convert_to_versions(service_release_history)
    latest_stable_by_minor = _latest_stable_release_by_minor(released_versions)

    # avoids re-fetching the same other-service history for custom policies
    other_service_history_cache: dict[str, list[ReleaseDBGet]] = {}

    for release in service_release_history:
        if release.compatibility_policy:
            compatibility = await _evaluate_custom_compatibility(
                product_name=product_name,
                user_id=user_id,
                repo=repo,
                target_version=release.version,
                released_versions=released_versions,
                compatibility_policy=dict(release.compatibility_policy),
                other_service_history_cache=other_service_history_cache,
            )
        else:
            compatibility = _evaluate_default_compatibility(
                as_version(release.version),
                released_versions,
                latest_stable_by_minor,
            )
        compatibility_map[release.version] = compatibility

    return compatibility_map
