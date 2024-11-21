from typing import Self

from pydantic import (
    AliasChoices,
    Field,
    PositiveInt,
    TypeAdapter,
    field_validator,
    model_validator,
)
from servicelib.logging_utils_filtering import LoggerName, MessageSubstring
from settings_library.base import BaseCustomSettings
from settings_library.basic_types import LogLevel, PortInt
from settings_library.postgres import PostgresSettings
from settings_library.redis import RedisSettings
from settings_library.s3 import S3Settings
from settings_library.tracing import TracingSettings
from settings_library.utils_logging import MixinLoggingSettings

from .datcore_adapter.datcore_adapter_settings import DatcoreAdapterSettings


class Settings(BaseCustomSettings, MixinLoggingSettings):
    STORAGE_HOST: str = "0.0.0.0"  # nosec
    STORAGE_PORT: PortInt = TypeAdapter(PortInt).validate_python(8080)

    LOG_LEVEL: LogLevel = Field(
        "INFO",
        validation_alias=AliasChoices("STORAGE_LOGLEVEL", "LOG_LEVEL", "LOGLEVEL"),
    )

    STORAGE_MAX_WORKERS: PositiveInt = Field(
        8,
        description="Number of workers for the thead executor pool used in DatcoreWrapper",
    )

    STORAGE_MONITORING_ENABLED: bool = False
    STORAGE_PROFILING: bool = False

    BF_API_KEY: str | None = Field(
        None, description="Pennsieve API key ONLY for testing purposes"
    )
    BF_API_SECRET: str | None = Field(
        None, description="Pennsieve API secret ONLY for testing purposes"
    )

    STORAGE_POSTGRES: PostgresSettings = Field(
        json_schema_extra={"auto_default_from_env": True}
    )

    STORAGE_REDIS: RedisSettings | None = Field(
        json_schema_extra={"auto_default_from_env": True}
    )

    STORAGE_S3: S3Settings = Field(json_schema_extra={"auto_default_from_env": True})

    STORAGE_TRACING: TracingSettings | None = Field(
        json_schema_extra={"auto_default_from_env": True}
    )

    DATCORE_ADAPTER: DatcoreAdapterSettings = Field(
        json_schema_extra={"auto_default_from_env": True}
    )

    STORAGE_SYNC_METADATA_TIMEOUT: PositiveInt = Field(
        180, description="Timeout (seconds) for metadata sync task"
    )

    STORAGE_DEFAULT_PRESIGNED_LINK_EXPIRATION_SECONDS: int = Field(
        3600, description="Default expiration time in seconds for presigned links"
    )

    STORAGE_CLEANER_INTERVAL_S: int | None = Field(
        30,
        description="Interval in seconds when task cleaning pending uploads runs. setting to NULL disables the cleaner.",
    )

    STORAGE_S3_CLIENT_MAX_TRANSFER_CONCURRENCY: int = Field(
        4,
        description="Maximal amount of threads used by underlying S3 client to transfer data to S3 backend",
    )

    STORAGE_LOG_FORMAT_LOCAL_DEV_ENABLED: bool = Field(
        default=False,
        validation_alias=AliasChoices(
            "STORAGE_LOG_FORMAT_LOCAL_DEV_ENABLED",
            "LOG_FORMAT_LOCAL_DEV_ENABLED",
        ),
        description="Enables local development log format. WARNING: make sure it is disabled if you want to have structured logs!",
    )
    STORAGE_LOG_FILTER_MAPPING: dict[LoggerName, list[MessageSubstring]] = Field(
        default_factory=dict,
        validation_alias=AliasChoices(
            "STORAGE_LOG_FILTER_MAPPING", "LOG_FILTER_MAPPING"
        ),
        description="is a dictionary that maps specific loggers (such as 'uvicorn.access' or 'gunicorn.access') to a list of log message patterns that should be filtered out.",
    )

    @field_validator("LOG_LEVEL", mode="before")
    @classmethod
    def _validate_loglevel(cls, value: str) -> str:
        log_level: str = cls.validate_log_level(value)
        return log_level

    @model_validator(mode="after")
    def ensure_settings_consistency(self) -> Self:
        if self.STORAGE_CLEANER_INTERVAL_S is not None and not self.STORAGE_REDIS:
            msg = (
                "STORAGE_CLEANER_INTERVAL_S cleaner cannot be set without STORAGE_REDIS! "
                "Please correct settings."
            )
            raise ValueError(msg)
        return self
