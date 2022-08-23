from typing import Final

from ..services import ServiceKey

# NOTE: due to legacy reasons, the name remains with 'frontend' in it but
# it now refers to a more general group: function sections that contains front-end services as well
FUNCTION_SERVICE_KEY_PREFIX: Final[str] = "simcore/services/frontend"


def is_function_service(service_key: ServiceKey) -> bool:
    return service_key.startswith(f"{FUNCTION_SERVICE_KEY_PREFIX}/")


def is_iterator_service(service_key: ServiceKey) -> bool:
    return service_key.startswith(f"{FUNCTION_SERVICE_KEY_PREFIX}/data-iterator/")
