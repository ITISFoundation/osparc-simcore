""" Manages service compatibility policies

"""

from copy import deepcopy

from models_library.services_history import Compatibility, ServiceRelease
from models_library.services_types import ServiceVersion
from packaging.specifiers import SpecifierSet
from packaging.version import Version
from simcore_service_catalog.utils.versioning import as_version


def _get_default_compatibility_specs(target: ServiceVersion | Version) -> SpecifierSet:
    version = as_version(target)

    newer_version_spec = SpecifierSet(f">{version}")
    patch_compatible_spec = SpecifierSet(
        f"~={version.major}.{version.minor}.{version.micro}"
    )
    return newer_version_spec & patch_compatible_spec


def _get_latest_first_releases(history: list[ServiceRelease]) -> list[Version]:
    return sorted(
        (as_version(h.version) for h in history if not h.retired),
        reverse=True,
    )


def _get_latest_compatible_version(
    target: ServiceVersion,
    latest_first_releases: list[Version],
    compatibility_specs: SpecifierSet | None = None,
) -> ServiceVersion | None:

    compatibility_specs = compatibility_specs or _get_default_compatibility_specs(
        target
    )
    for v in compatibility_specs.filter(latest_first_releases):
        return ServiceVersion(f"{v}")
    return None


def update_compatibility(history: list[ServiceRelease]) -> list[ServiceRelease]:
    updated_history = deepcopy(history)
    latest_first_releases = _get_latest_first_releases(history)

    for release in updated_history:
        if v := _get_latest_compatible_version(release.version, latest_first_releases):
            release.compatibility = Compatibility(can_update_to=v)
    return updated_history
