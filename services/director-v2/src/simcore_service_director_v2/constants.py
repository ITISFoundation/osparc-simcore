from typing import Final

from models_library.api_schemas_directorv2.services import (
    DYNAMIC_PROXY_SERVICE_PREFIX,
    DYNAMIC_SIDECAR_SERVICE_PREFIX,
)

# dynamic services

# label storing scheduler_data to allow service
# monitoring recovery after director-v2 reboots
DYNAMIC_SIDECAR_SCHEDULER_DATA_LABEL: Final[str] = "io.simcore.scheduler-data"

# This matches registries by:
# - local
# - itisfoundation
# - 10.0.0.0:8473 (IP & Port)
DYNAMIC_SIDECAR_DOCKER_IMAGE_RE: Final[str] = (
    r"^(([_a-zA-Z0-9:.-]+)/)?(dynamic-sidecar):([_a-zA-Z0-9.-]+)$"
)

LOGS_FILE_NAME: Final[str] = "logs.zip"

REGEX_DY_SERVICE_SIDECAR: Final[str] = (
    rf"^{DYNAMIC_SIDECAR_SERVICE_PREFIX}_[a-zA-Z0-9-_]*"
)
REGEX_DY_SERVICE_PROXY: Final[str] = rf"^{DYNAMIC_PROXY_SERVICE_PREFIX}_[a-zA-Z0-9-_]*"

UNDEFINED_STR_METADATA: Final[str] = "undefined-metadata"
UNDEFINED_DOCKER_LABEL: Final[str] = "undefined-label"
UNDEFINED_API_BASE_URL: Final[str] = "https://api.local"
