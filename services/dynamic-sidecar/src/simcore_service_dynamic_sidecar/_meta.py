""" Package Metadata

"""
from contextlib import suppress

import pkg_resources

_current_distribution = pkg_resources.get_distribution(
    "simcore-service-dynamic-sidecar"
)

PROJECT_NAME: str = _current_distribution.project_name

API_VERSION: str = _current_distribution.version
MAJOR, MINOR, PATCH = _current_distribution.version.split(".")
API_VTAG: str = f"v{MAJOR}"

__version__ = _current_distribution.version


def get_summary() -> str:
    with suppress(Exception):
        try:
            metadata = _current_distribution.get_metadata_lines("METADATA")
        except FileNotFoundError:
            metadata = _current_distribution.get_metadata_lines("PKG-INFO")

        return next(x.split(":") for x in metadata if x.startswith("Summary:"))[-1]
    return ""


SUMMARY: str = get_summary()
