""" Manages service compatibility policies

"""
from models_library.services_history import ServiceRelease
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
    latest_patch_release = sorted(
        v for v in versions if current_version < v and _is_patch(current_version, v)
    )
    return (
        ServiceVersion(f"{latest_patch_release[0]}") if latest_patch_release else None
    )
