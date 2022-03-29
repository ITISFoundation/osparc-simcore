from typing import Callable, Dict, Tuple

from models_library.function_services_catalog import iter_service_docker_data
from models_library.services import ServiceDockerData, ServiceKey, ServiceVersion
from pydantic import validate_arguments

_ServiceKeyVersionPair = Tuple[str, str]


# META-FUNCTIONS ---------------------------------------------------

# Catalog of front-end (i.e. non-docker) services
FUNCTION_SERVICES_CATALOG: Dict[_ServiceKeyVersionPair, ServiceDockerData] = {
    (s.key, s.version): s for s in iter_service_docker_data()
}


FUNCTION_SERVICE_TO_CALLABLE: Dict[_ServiceKeyVersionPair, Callable] = {}


@validate_arguments
def register_implementation(name: ServiceKey, version: ServiceVersion) -> Callable:
    """Maps a service with a callable

    Basically "glues" the implementation to a function node
    """
    key: _ServiceKeyVersionPair = (name, version)

    if key not in FUNCTION_SERVICES_CATALOG.keys():
        raise ValueError(
            f"No definition of {key} found in the {len(FUNCTION_SERVICES_CATALOG)=}"
        )

    if key in FUNCTION_SERVICE_TO_CALLABLE.keys():
        raise ValueError(f"{key} is already registered")

    def _decorator(func: Callable):
        # TODO: ensure inputs/outputs map function signature
        FUNCTION_SERVICE_TO_CALLABLE[key] = func

        # TODO: wrapper(args,kwargs): extract schemas for inputs and use them to validate inputs
        # before running

        return func

    return _decorator
