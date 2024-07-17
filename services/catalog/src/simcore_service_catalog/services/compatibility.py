""" Manages service compatibility policies

"""
from copy import deepcopy

from models_library.services_history import Compatibility, ServiceRelease
from models_library.services_types import ServiceVersion
from packaging.specifiers import SpecifierSet
from packaging.version import Version
from simcore_service_catalog.utils.versioning import as_version


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
    latest_first_releases: list[Version],
    compatibility_specs: SpecifierSet | None = None,
) -> Version | None:
    """
    Returns latest version in history that satisfies `>X.Y.Z, ~=X.Y.Z` (default policy if compatibility_specs=None) or compatibility_specs
    Returns None if no version in history satisfies specs.
    """

    compatibility_specs = compatibility_specs or _get_default_compatibility_specs(
        target
    )
    for v in compatibility_specs.filter(latest_first_releases):
        return v
    return None


def update_compatibility(history: list[ServiceRelease]) -> list[ServiceRelease]:
    updated_history = deepcopy(history)

    latest_first_releases = sorted(
        (as_version(h.version) for h in history if not h.retired),
        reverse=True,
    )

    for release in updated_history:
        if v := _get_latest_compatible_version(release.version, latest_first_releases):
            release.compatibility = Compatibility(can_update_to=f"{v}")
    return updated_history
