import datetime
from functools import cached_property

from models_library.basic_types import BootModeEnum
from pydantic import AliasChoices, Field, PositiveInt, field_validator
from servicelib.logging_utils_filtering import LoggerName, MessageSubstring
from settings_library.base import BaseCustomSettings
from settings_library.basic_types import BuildTargetEnum, LogLevel, VersionTag
from settings_library.postgres import PostgresSettings
from settings_library.prometheus import PrometheusSettings
from settings_library.rabbit import RabbitSettings
from settings_library.redis import RedisSettings
from settings_library.s3 import S3Settings
from settings_library.tracing import TracingSettings
from settings_library.utils_logging import MixinLoggingSettings

from .._meta import API_VERSION, API_VTAG, PROJECT_NAME


class _BaseApplicationSettings(BaseCustomSettings, MixinLoggingSettings):
    # CODE STATICS ---------------------------------------------------------
    API_VERSION: str = API_VERSION
    APP_NAME: str = PROJECT_NAME
    API_VTAG: VersionTag = API_VTAG

    # IMAGE BUILDTIME ------------------------------------------------------
    # @Makefile
    SC_BUILD_DATE: str | None = None
    SC_BUILD_TARGET: BuildTargetEnum | None = None
    SC_VCS_REF: str | None = None
    SC_VCS_URL: str | None = None

    # @Dockerfile
    SC_BOOT_MODE: BootModeEnum | None = None
    SC_BOOT_TARGET: BuildTargetEnum | None = None
    SC_HEALTHCHECK_TIMEOUT: PositiveInt | None = Field(
        default=None,
        description="If a single run of the check takes longer than timeout seconds "
        "then the check is considered to have failed."
        "It takes retries consecutive failures of the health check for the container to be considered unhealthy.",
    )
    SC_USER_ID: int | None = None
    SC_USER_NAME: str | None = None

    # RUNTIME  -----------------------------------------------------------
    RESOURCE_USAGE_TRACKER_DEBUG: bool = Field(
        default=False,
        description="Debug mode",
        validation_alias=AliasChoices(
            "RESOURCE_USAGE_TRACKER_DEBUG",
            "DEBUG",
        ),
    )
    RESOURCE_USAGE_TRACKER_LOGLEVEL: LogLevel = Field(
        default=LogLevel.INFO,
        validation_alias=AliasChoices(
            "RESOURCE_USAGE_TRACKER_LOGLEVEL", "LOG_LEVEL", "LOGLEVEL"
        ),
    )
    RESOURCE_USAGE_TRACKER_LOG_FORMAT_LOCAL_DEV_ENABLED: bool = Field(
        default=False,
        validation_alias=AliasChoices(
            "RESOURCE_USAGE_TRACKER_LOG_FORMAT_LOCAL_DEV_ENABLED",
            "LOG_FORMAT_LOCAL_DEV_ENABLED",
        ),
        description="Enables local development log format. WARNING: make sure it is disabled if you want to have structured logs!",
    )
    RESOURCE_USAGE_TRACKER_LOG_FILTER_MAPPING: dict[
        LoggerName, list[MessageSubstring]
    ] = Field(
        default_factory=dict,
        validation_alias=AliasChoices(
            "RESOURCE_USAGE_TRACKER_LOG_FILTER_MAPPING", "LOG_FILTER_MAPPING"
        ),
        description="is a dictionary that maps specific loggers (such as 'uvicorn.access' or 'gunicorn.access') to a list of log message patterns that should be filtered out.",
    )

    @cached_property
    def LOG_LEVEL(self) -> LogLevel:  # noqa: N802
        return self.RESOURCE_USAGE_TRACKER_LOGLEVEL

    @field_validator("RESOURCE_USAGE_TRACKER_LOGLEVEL", mode="before")
    @classmethod
    def valid_log_level(cls, value: str) -> str:
        return cls.validate_log_level(value)


class MinimalApplicationSettings(_BaseApplicationSettings):
    """Extends base settings with the settings needed to connect with prometheus/DB

    Separated for convenience to run some commands of the CLI that
    are not related to the web server.
    """

    RESOURCE_USAGE_TRACKER_PROMETHEUS: PrometheusSettings | None = Field(
        json_schema_extra={"auto_default_from_env": True}
    )

    RESOURCE_USAGE_TRACKER_POSTGRES: PostgresSettings | None = Field(
        json_schema_extra={"auto_default_from_env": True},
    )

    RESOURCE_USAGE_TRACKER_REDIS: RedisSettings = Field(
        json_schema_extra={"auto_default_from_env": True},
    )
    RESOURCE_USAGE_TRACKER_RABBITMQ: RabbitSettings | None = Field(
        json_schema_extra={"auto_default_from_env": True},
    )


class ApplicationSettings(MinimalApplicationSettings):
    """Web app's environment variables

    These settings includes extra configuration for the http-API
    """

    RESOURCE_USAGE_TRACKER_MISSED_HEARTBEAT_CHECK_ENABLED: bool = Field(
        default=True,
        description="Possibility to disable RUT background task for checking heartbeats.",
    )
    RESOURCE_USAGE_TRACKER_MISSED_HEARTBEAT_INTERVAL_SEC: datetime.timedelta = Field(
        default=datetime.timedelta(minutes=5),
        description="Interval to check heartbeat of running services. (default to seconds, or see https://pydantic-docs.helpmanual.io/usage/types/#datetime-types for string formating)",
    )
    RESOURCE_USAGE_TRACKER_MISSED_HEARTBEAT_COUNTER_FAIL: int = Field(
        default=6,
        description="Heartbeat couter limit when RUT considers service as unhealthy.",
    )
    RESOURCE_USAGE_TRACKER_PROMETHEUS_INSTRUMENTATION_ENABLED: bool = True
    RESOURCE_USAGE_TRACKER_S3: S3Settings | None = Field(
        json_schema_extra={"auto_default_from_env": True},
    )
    RESOURCE_USAGE_TRACKER_TRACING: TracingSettings | None = Field(
        description="settings for opentelemetry tracing",
        json_schema_extra={"auto_default_from_env": True},
    )

    @field_validator(
        "RESOURCE_USAGE_TRACKER_MISSED_HEARTBEAT_INTERVAL_SEC", mode="before"
    )
    @classmethod
    def _validate_interval(cls, v):
        if isinstance(v, str) and v.isnumeric():
            return int(v)
        return v
