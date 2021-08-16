import pkg_resources

current_distribution = pkg_resources.get_distribution("simcore_service_dynamic_sidecar")

api_vtag = "v1"
__version__ = current_distribution.version
