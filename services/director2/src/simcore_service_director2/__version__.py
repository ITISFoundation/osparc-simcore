""" Current version of the simcore_service_director2 application.
"""
import pkg_resources

__version__ = pkg_resources.get_distribution("simcore_service_director2").version

major, minor, patch = __version__.split(".")

api_version: str = __version__
api_vtag: str = f"v{major}"
