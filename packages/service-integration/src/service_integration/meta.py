import pkg_resources

current_distribution = pkg_resources.get_distribution("simcore-service-integration")
project_name: str = current_distribution.project_name
__version__ = current_distribution.version

# TODO: this needs to sync with sidecar integration interface
INTEGRATION_API_VERSION = "1.0.0"
