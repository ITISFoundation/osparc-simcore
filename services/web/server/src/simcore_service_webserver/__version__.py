""" Current version of the simcore_service_webserver application and its API

"""
import pkg_resources

from semantic_version import Version

__version__: str = pkg_resources.get_distribution("simcore_service_webserver").version

version = Version(__version__)

api_version_prefix: str = f"v{version.major}"
