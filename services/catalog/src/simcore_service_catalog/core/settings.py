import logging
from functools import cached_property
from typing import Optional

from models_library.basic_types import BootModeEnum, BuildTargetEnum, LogLevel
from models_library.services_resources import ServiceResources
from pydantic import ByteSize, Field, PositiveInt
from settings_library.base import BaseCustomSettings
from settings_library.http_client_request import ClientRequestSettings
from settings_library.postgres import PostgresSettings
from settings_library.tracing import TracingSettings
from settings_library.utils_logging import MixinLoggingSettings

logger = logging.getLogger(__name__)


class DirectorSettings(BaseCustomSettings):
    DIRECTOR_HOST: str
    DIRECTOR_PORT: int = 8080
    DIRECTOR_VTAG: str = "v0"

    @cached_property
    def base_url(self) -> str:
        return f"http://{self.DIRECTOR_HOST}:{self.DIRECTOR_PORT}/{self.DIRECTOR_VTAG}"


_DEFAULT_SERVICE_RESOURCES = ServiceResources.parse_obj(
    {
        "CPU": {"limit": 0.1, "reservation": 0.1},
        "RAM": {
            "limit": ByteSize(2 * 1024**3),
            "reservation": ByteSize(2 * 1024**3),
        },
    }
)


class AppSettings(BaseCustomSettings, MixinLoggingSettings):
    # docker environs
    SC_BOOT_MODE: Optional[BootModeEnum]
    SC_BOOT_TARGET: Optional[BuildTargetEnum]

    CATALOG_LOG_LEVEL: LogLevel = Field(
        LogLevel.INFO.value,
        env=["CATALOG_LOGLEVEL", "LOG_LEVEL", "LOGLEVEL"],
    )
    CATALOG_DEV_FEATURES_ENABLED: bool = Field(
        False,
        description="Enables development features. WARNING: make sure it is disabled in production .env file!",
    )

    CATALOG_POSTGRES: Optional[PostgresSettings] = Field(auto_default_from_env=True)

    CATALOG_CLIENT_REQUEST: Optional[ClientRequestSettings] = Field(
        auto_default_from_env=True
    )

    CATALOG_DIRECTOR: Optional[DirectorSettings] = Field(auto_default_from_env=True)

    # BACKGROUND TASK
    CATALOG_BACKGROUND_TASK_REST_TIME: PositiveInt = 60
    CATALOG_BACKGROUND_TASK_WAIT_AFTER_FAILURE: PositiveInt = 5  # secs
    CATALOG_ACCESS_RIGHTS_DEFAULT_PRODUCT_NAME: str = "osparc"

    CATALOG_TRACING: Optional[TracingSettings] = None

    CATALOG_SERVICES_DEFAULT_RESOURCE: ServiceResources = _DEFAULT_SERVICE_RESOURCES
