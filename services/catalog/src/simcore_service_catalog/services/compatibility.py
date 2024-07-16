""" Manages service compatibility policies

"""
from copy import deepcopy

from models_library.services_history import Compatibility, ServiceRelease
from models_library.services_types import ServiceVersion
from packages.version import Version
from simcore_service_catalog.utils.versioning import as_version


def _is_patch(v: Version, r: Version) -> bool:
    return v.major == r.major and v.minor == r.minor and v.micro != r.micro


def get_latest_compatible_version(
    version: ServiceVersion, history: list[ServiceRelease]
) -> ServiceVersion | None:
    current_version = as_version(version)
    versions = [as_version(item.version) for item in history if not item.retired]
    patches = sorted(
        v for v in versions if current_version < v and _is_patch(current_version, v)
    )
    return ServiceVersion(f"{patches[-1]}") if patches else None


def update_compatibility(history: list[ServiceRelease]) -> list[ServiceRelease]:
    updated_history = deepcopy(history)
    for item in updated_history:
        if v := get_latest_compatible_version(item.version, history):
            item.compatibility = Compatibility(can_update_to=v)
    return updated_history
