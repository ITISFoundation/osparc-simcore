from types import MappingProxyType
from typing import Final

from .services_enums import ServiceType

LATEST_INTEGRATION_VERSION: Final[str] = "1.0.0"

ANY_FILETYPE: Final[str] = "data:*/*"

SERVICE_TYPE_TO_NAME_MAP = MappingProxyType(
    {
        ServiceType.COMPUTATIONAL: "comp",
        ServiceType.DYNAMIC: "dynamic",
        ServiceType.FRONTEND: "frontend",
    }
)


def _create_key_prefix(service_type: ServiceType) -> str:
    return f"simcore/services/{SERVICE_TYPE_TO_NAME_MAP[service_type]}"


COMPUTATIONAL_SERVICE_KEY_PREFIX: Final[str] = _create_key_prefix(
    ServiceType.COMPUTATIONAL
)
DYNAMIC_SERVICE_KEY_PREFIX: Final[str] = _create_key_prefix(ServiceType.DYNAMIC)
FRONTEND_SERVICE_KEY_PREFIX: Final[str] = _create_key_prefix(ServiceType.FRONTEND)
