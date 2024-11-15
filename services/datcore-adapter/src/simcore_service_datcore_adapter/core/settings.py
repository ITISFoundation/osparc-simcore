from functools import cached_property

from models_library.basic_types import BootModeEnum, LogLevel
from pydantic import AliasChoices, Field, TypeAdapter, field_validator
from pydantic.networks import AnyUrl
from servicelib.logging_utils_filtering import LoggerName, MessageSubstring
from settings_library.application import BaseApplicationSettings
from settings_library.base import BaseCustomSettings
from settings_library.tracing import TracingSettings
from settings_library.utils_logging import MixinLoggingSettings


class PennsieveSettings(BaseCustomSettings):
    PENNSIEVE_ENABLED: bool = True

    PENNSIEVE_API_URL: AnyUrl = TypeAdapter(AnyUrl).validate_python(
        "https://api.pennsieve.io"
    )
    PENNSIEVE_API_GENERAL_TIMEOUT: float = 20.0
    PENNSIEVE_HEALTCHCHECK_TIMEOUT: float = 1.0


class ApplicationSettings(BaseApplicationSettings, MixinLoggingSettings):
    LOG_LEVEL: LogLevel = Field(
        default=LogLevel.INFO.value,
        validation_alias=AliasChoices(
            "DATCORE_ADAPTER_LOGLEVEL",
            "DATCORE_ADAPTER_LOG_LEVEL",
            "LOG_LEVEL",
            "LOGLEVEL",
        ),
    )

    PENNSIEVE: PennsieveSettings = Field(
        json_schema_extra={"auto_default_from_env": True}
    )

    DATCORE_ADAPTER_LOG_FORMAT_LOCAL_DEV_ENABLED: bool = Field(
        default=False,
        validation_alias=AliasChoices(
            "DATCORE_ADAPTER_LOG_FORMAT_LOCAL_DEV_ENABLED",
            "LOG_FORMAT_LOCAL_DEV_ENABLED",
        ),
        description="Enables local development log format. WARNING: make sure it is disabled if you want to have structured logs!",
    )
    DATCORE_ADAPTER_LOG_FILTER_MAPPING: dict[
        LoggerName, list[MessageSubstring]
    ] = Field(
        default_factory=dict,
        validation_alias=AliasChoices(
            "DATCORE_ADAPTER_LOG_FILTER_MAPPING", "LOG_FILTER_MAPPING"
        ),
        description="is a dictionary that maps specific loggers (such as 'uvicorn.access' or 'gunicorn.access') to a list of log message patterns that should be filtered out.",
    )
    DATCORE_ADAPTER_PROMETHEUS_INSTRUMENTATION_ENABLED: bool = True
    DATCORE_ADAPTER_TRACING: TracingSettings | None = Field(
        description="settings for opentelemetry tracing",
        json_schema_extra={"auto_default_from_env": True},
    )

    @cached_property
    def debug(self) -> bool:
        """If True, debug tracebacks should be returned on errors."""
        return self.SC_BOOT_MODE in [
            BootModeEnum.DEBUG,
            BootModeEnum.DEVELOPMENT,
            BootModeEnum.LOCAL,
        ]

    @field_validator("LOG_LEVEL", mode="before")
    @classmethod
    def _validate_loglevel(cls, value: str) -> str:
        return cls.validate_log_level(value)
