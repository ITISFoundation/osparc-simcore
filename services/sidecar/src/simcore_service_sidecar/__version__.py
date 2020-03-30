""" Current version of the simcore_service_api_gateway application
"""
import pkg_resources

__version__ = pkg_resources.get_distribution("simcore_service_sidecar").version

major, minor, patch = __version__.split(".")

api_version = __version__
api_version_prefix: str = f"v{major}"