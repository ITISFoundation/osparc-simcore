""" Application's metadata

"""
from contextlib import suppress
from typing import Final

import pkg_resources

_current_distribution = pkg_resources.get_distribution("simcore_service_autoscaling")

PROJECT_NAME: Final[str] = _current_distribution.project_name

API_VERSION: Final[str] = _current_distribution.version
MAJOR, MINOR, PATCH = _current_distribution.version.split(".")
API_VTAG: Final[str] = f"v{MAJOR}"

__version__: Final[str] = API_VERSION


def get_summary() -> str:
    with suppress(Exception):
        try:
            metadata = _current_distribution.get_metadata_lines("METADATA")
        except FileNotFoundError:
            metadata = _current_distribution.get_metadata_lines("PKG-INFO")

        return next(x.split(":") for x in metadata if x.startswith("Summary:"))[-1]
    return ""


SUMMARY: Final[str] = get_summary()
