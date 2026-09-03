from typing import Final

from models_library.products import ProductName

SERVICE_RUNTIME_SETTINGS: Final[str] = "simcore.service.settings"
SERVICE_REVERSE_PROXY_SETTINGS: Final[str] = "simcore.service.reverse-proxy-settings"
SERVICE_RUNTIME_BOOTSETTINGS: Final[str] = "simcore.service.bootsettings"


APP_REGISTRY_CACHE_DATA_KEY: Final[str] = __name__ + "_registry_cache_data"

API_ROOT: Final[str] = "api"

DIRECTOR_SIMCORE_SERVICES_PREFIX: Final[str] = "simcore/services"

DATETIME_FORMAT: Final[str] = "%Y-%m-%dT%H:%M:%S.%f"

LEGACY_SERVICES_PINNED_OSPARC_PRODUCT: Final[ProductName] = "osparc"
