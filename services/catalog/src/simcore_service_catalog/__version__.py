import pkg_resources

__version__ = pkg_resources.get_distribution("simcore_service_catalog").version

major, minor, patch = __version__.split(".")

api_version = __version__
api_vtag: str = f"v{major}"
