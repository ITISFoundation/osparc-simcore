""" Package Metadata

"""
import pkg_resources

current_distribution = pkg_resources.get_distribution("simcore_service_catalog")

project_name: str = current_distribution.project_name

api_version: str = current_distribution.version
major, minor, patch = current_distribution.version.split(".")
api_vtag: str = f"v{major}"

__version__ = current_distribution.version


try:
    metadata = current_distribution.get_metadata_lines("METADATA")
except FileNotFoundError:
    metadata = current_distribution.get_metadata_lines("PKG-INFO")

summary: str = next(
    x.split(":")
    for x in metadata
    if x.startswith("Summary:")
)[-1]
