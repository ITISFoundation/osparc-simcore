""" Manages service compatibility policies

"""
from copy import deepcopy

from models_library.services_history import Compatibility, ServiceRelease
from models_library.services_types import ServiceVersion
from packaging.specifiers import SpecifierSet
from packaging.version import Version
from simcore_service_catalog.utils.versioning import as_version


def _get_default_compatibility_specs(target: ServiceVersion | Version) -> SpecifierSet:
    """
        The current policy is `patch-compatible` and strictly enforces `newer versions`.

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
    """Returns the latest released version compatible with `target`, or None if an update is not possible."""

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
