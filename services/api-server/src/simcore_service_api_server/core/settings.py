from functools import cached_property
from typing import Annotated

from models_library.basic_types import BootModeEnum, LogLevel
from pydantic import (
    AliasChoices,
    Field,
    NonNegativeInt,
    PositiveInt,
    SecretStr,
    field_validator,
)
from servicelib.logging_utils_filtering import LoggerName, MessageSubstring
from settings_library.base import BaseCustomSettings
from settings_library.catalog import CatalogSettings
from settings_library.director_v2 import DirectorV2Settings
from settings_library.postgres import PostgresSettings
from settings_library.rabbit import RabbitSettings
from settings_library.storage import StorageSettings
from settings_library.tracing import TracingSettings
from settings_library.utils_logging import MixinLoggingSettings
from settings_library.utils_session import (
    DEFAULT_SESSION_COOKIE_NAME,
    MixinSessionSettings,
)
from settings_library.webserver import WebServerSettings as WebServerBaseSettings


class WebServerSettings(WebServerBaseSettings, MixinSessionSettings):

    WEBSERVER_SESSION_SECRET_KEY: SecretStr = Field(
        ...,
        description="Secret key to encrypt cookies. "
        'TIP: python3 -c "from cryptography.fernet import *; print(Fernet.generate_key())"',
        min_length=44,
        validation_alias=AliasChoices(
            "SESSION_SECRET_KEY", "WEBSERVER_SESSION_SECRET_KEY"
        ),
    )
    WEBSERVER_SESSION_NAME: str = DEFAULT_SESSION_COOKIE_NAME

    @field_validator("WEBSERVER_SESSION_SECRET_KEY")
    @classmethod
    def check_valid_fernet_key(cls, v):
        return cls.do_check_valid_fernet_key(v)


# MAIN SETTINGS --------------------------------------------


class BasicSettings(BaseCustomSettings, MixinLoggingSettings):
    # DEVELOPMENT
    API_SERVER_DEV_FEATURES_ENABLED: bool = Field(
        default=False,
        validation_alias=AliasChoices(
            "API_SERVER_DEV_FEATURES_ENABLED", "FAKE_API_SERVER_ENABLED"
        ),
    )

    # LOGGING
    LOG_LEVEL: LogLevel = Field(
        default=LogLevel.INFO.value,
        validation_alias=AliasChoices("API_SERVER_LOGLEVEL", "LOG_LEVEL", "LOGLEVEL"),
    )
    API_SERVER_LOG_FORMAT_LOCAL_DEV_ENABLED: bool = Field(
        default=False,
        validation_alias=AliasChoices(
            "API_SERVER_LOG_FORMAT_LOCAL_DEV_ENABLED", "LOG_FORMAT_LOCAL_DEV_ENABLED"
        ),
        description="Enables local development log format. WARNING: make sure it is disabled if you want to have structured logs!",
    )
    API_SERVER_LOG_FILTER_MAPPING: dict[LoggerName, list[MessageSubstring]] = Field(
        default_factory=dict,
        validation_alias=AliasChoices(
            "API_SERVER_LOG_FILTER_MAPPING", "LOG_FILTER_MAPPING"
        ),
        description="is a dictionary that maps specific loggers (such as 'uvicorn.access' or 'gunicorn.access') to a list of log message patterns that should be filtered out.",
    )

    @field_validator("LOG_LEVEL", mode="before")
    @classmethod
    def _validate_loglevel(cls, value) -> str:
        log_level: str = cls.validate_log_level(value)
        return log_level


class ApplicationSettings(BasicSettings):
    # DOCKER BOOT
    SC_BOOT_MODE: BootModeEnum | None = None

    API_SERVER_POSTGRES: Annotated[
        PostgresSettings | None,
        Field(json_schema_extra={"auto_default_from_env": True}),
    ]

    API_SERVER_RABBITMQ: RabbitSettings | None = Field(
        json_schema_extra={"auto_default_from_env": True},
        description="settings for service/rabbitmq",
    )

    # SERVICES with http API
    API_SERVER_WEBSERVER: WebServerSettings | None = Field(
        json_schema_extra={"auto_default_from_env": True}
    )
    API_SERVER_CATALOG: CatalogSettings | None = Field(
        json_schema_extra={"auto_default_from_env": True}
    )
    API_SERVER_STORAGE: StorageSettings | None = Field(
        json_schema_extra={"auto_default_from_env": True}
    )
    API_SERVER_DIRECTOR_V2: DirectorV2Settings | None = Field(
        json_schema_extra={"auto_default_from_env": True}
    )
    API_SERVER_LOG_CHECK_TIMEOUT_SECONDS: NonNegativeInt = 3 * 60
    API_SERVER_PROMETHEUS_INSTRUMENTATION_ENABLED: bool = True
    API_SERVER_HEALTH_CHECK_TASK_PERIOD_SECONDS: PositiveInt = 30
    API_SERVER_HEALTH_CHECK_TASK_TIMEOUT_SECONDS: PositiveInt = 10
    API_SERVER_ALLOWED_HEALTH_CHECK_FAILURES: PositiveInt = 5
    API_SERVER_PROMETHEUS_INSTRUMENTATION_COLLECT_SECONDS: PositiveInt = 5
    API_SERVER_PROFILING: bool = False
    API_SERVER_TRACING: TracingSettings | None = Field(
        description="settings for opentelemetry tracing",
        json_schema_extra={"auto_default_from_env": True},
    )

    @cached_property
    def debug(self) -> bool:
        """If True, debug tracebacks should be returned on errors."""
        return self.SC_BOOT_MODE is not None and self.SC_BOOT_MODE.is_devel_mode()


__all__: tuple[str, ...] = (
    "ApplicationSettings",
    "BasicSettings",
    "CatalogSettings",
    "DirectorV2Settings",
    "StorageSettings",
    "WebServerSettings",
    "WebServerSettings",
)
