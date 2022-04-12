from typing import Final

# NOTE: due to legacy reasons, the name remains with 'frontend' in it but
# it now refers to a more general group: function sections that contains front-end services as well
FUNCTION_SERVICE_KEY_PREFIX: Final[str] = "simcore/services/frontend"


def is_function_service(service_key: str) -> bool:
    return service_key.startswith(f"{FUNCTION_SERVICE_KEY_PREFIX}/")


def is_parameter_service(service_key: str) -> bool:
    return service_key.startswith(f"{FUNCTION_SERVICE_KEY_PREFIX}/parameter/")


def is_iterator_service(service_key: str) -> bool:
    return service_key.startswith(f"{FUNCTION_SERVICE_KEY_PREFIX}/data-iterator/")


def is_iterator_consumer_service(service_key: str) -> bool:
    return service_key.startswith(f"{FUNCTION_SERVICE_KEY_PREFIX}/iterator-consumer/")
