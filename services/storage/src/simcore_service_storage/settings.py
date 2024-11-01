from typing import Any

from pydantic import Field, PositiveInt, root_validator, validator
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
    STORAGE_PORT: PortInt = PortInt(8080)

    LOG_LEVEL: LogLevel = Field(
        "INFO", env=["STORAGE_LOGLEVEL", "LOG_LEVEL", "LOGLEVEL"]
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

    STORAGE_POSTGRES: PostgresSettings = Field(auto_default_from_env=True)

    STORAGE_REDIS: RedisSettings | None = Field(auto_default_from_env=True)

    STORAGE_S3: S3Settings = Field(auto_default_from_env=True)

    STORAGE_TRACING: TracingSettings | None = Field(auto_default_from_env=True)

    DATCORE_ADAPTER: DatcoreAdapterSettings = Field(auto_default_from_env=True)

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
        False,
        env=["STORAGE_LOG_FORMAT_LOCAL_DEV_ENABLED", "LOG_FORMAT_LOCAL_DEV_ENABLED"],
        description="Enables local development log format. WARNING: make sure it is disabled if you want to have structured logs!",
    )
    STORAGE_LOG_FILTER_MAPPING: dict[LoggerName, list[MessageSubstring]] = Field(
        default_factory=dict,
        env=["STORAGE_LOG_FILTER_MAPPING", "LOG_FILTER_MAPPING"],
        description="is a dictionary that maps specific loggers (such as 'uvicorn.access' or 'gunicorn.access') to a list of log message patterns that should be filtered out.",
    )

    @validator("LOG_LEVEL")
    @classmethod
    def _validate_loglevel(cls, value) -> str:
        log_level: str = cls.validate_log_level(value)
        return log_level

    @root_validator()
    @classmethod
    def ensure_settings_consistency(cls, values: dict[str, Any]):
        if values.get("STORAGE_CLEANER_INTERVAL_S") and not values.get("STORAGE_REDIS"):
            raise ValueError(
                "STORAGE_CLEANER_INTERVAL_S cleaner cannot be set without STORAGE_REDIS! Please correct settings."
            )
        return values
