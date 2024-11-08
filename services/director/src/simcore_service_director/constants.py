from typing import Final

SERVICE_RUNTIME_SETTINGS: Final[str] = "simcore.service.settings"
SERVICE_REVERSE_PROXY_SETTINGS: Final[str] = "simcore.service.reverse-proxy-settings"
SERVICE_RUNTIME_BOOTSETTINGS: Final[str] = "simcore.service.bootsettings"

ORG_LABELS_TO_SCHEMA_LABELS: Final[dict[str, str]] = {
    "org.label-schema.build-date": "build_date",
    "org.label-schema.vcs-ref": "vcs_ref",
    "org.label-schema.vcs-url": "vcs_url",
}


CPU_RESOURCE_LIMIT_KEY: Final[str] = "SIMCORE_NANO_CPUS_LIMIT"
MEM_RESOURCE_LIMIT_KEY: Final[str] = "SIMCORE_MEMORY_BYTES_LIMIT"

APP_REGISTRY_CACHE_DATA_KEY: Final[str] = __name__ + "_registry_cache_data"

API_ROOT: Final[str] = "api"

DIRECTOR_SIMCORE_SERVICES_PREFIX: Final[str] = "simcore/services"

DATETIME_FORMAT: Final[str] = "%Y-%m-%dT%H:%M:%S.%f"
