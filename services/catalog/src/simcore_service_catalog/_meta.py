""" Package Metadata

"""
import pkg_resources

_current_distribution = pkg_resources.get_distribution("simcore_service_catalog")

PROJECT_NAME: str = _current_distribution.project_name

API_VERSION: str = _current_distribution.version
MAJOR, MINOR, PATCH = _current_distribution.version.split(".")
API_VTAG: str = f"v{MAJOR}"

__version__ = _current_distribution.version


try:
    metadata = _current_distribution.get_metadata_lines("METADATA")
except FileNotFoundError:
    metadata = _current_distribution.get_metadata_lines("PKG-INFO")

SUMMARY: str = next(x.split(":") for x in metadata if x.startswith("Summary:"))[-1]
