""" Application's metadata

"""
from contextlib import suppress
from typing import Final

import pkg_resources

current_distribution = pkg_resources.get_distribution("simcore_service_datcore_adapter")

__version__ = current_distribution.version

API_VERSION: Final[str] = __version__
MAJOR, MINOR, PATCH = __version__.split(".")
API_VTAG: Final[str] = f"v{MAJOR}"
PROJECT_NAME: Final[str] = current_distribution.project_name


def get_summary() -> str:
    with suppress(Exception):
        try:
            metadata = current_distribution.get_metadata_lines("METADATA")
        except FileNotFoundError:
            metadata = current_distribution.get_metadata_lines("PKG-INFO")

        return next(x.split(":") for x in metadata if x.startswith("Summary:"))[-1]
    return ""


summary: str = get_summary()
