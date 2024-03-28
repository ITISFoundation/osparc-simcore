from importlib.metadata import distribution, version

from models_library.services import LATEST_INTEGRATION_VERSION

current_distribution = distribution("simcore-service-integration")
project_name: str = current_distribution.metadata["Name"]
__version__ = version("simcore-service-integration")


INTEGRATION_API_VERSION = "1.0.0"

# If this fails, adapt integration configs!
assert LATEST_INTEGRATION_VERSION == INTEGRATION_API_VERSION  # nosec
