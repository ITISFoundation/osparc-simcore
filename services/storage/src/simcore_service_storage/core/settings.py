from datetime import timedelta
from typing import Annotated

from annotated_types import Gt
from celery_library.basic_types import BootServerMode
from common_library.logging.logging_utils_filtering import LoggerName, MessageSubstring
from fastapi import FastAPI
from pydantic import (
    AliasChoices,
    Field,
    PositiveInt,
    field_validator,
)
from settings_library.application import BaseApplicationSettings
from settings_library.base import BaseCustomSettings
from settings_library.basic_types import LogLevel, PortInt
from settings_library.celery import CelerySettings
from settings_library.postgres import PostgresSettings
from settings_library.rabbit import RabbitSettings
from settings_library.redis import RedisSettings
from settings_library.s3 import S3Settings
from settings_library.tracing import TracingSettings
from settings_library.utils_logging import MixinLoggingSettings

from ..modules.datcore_adapter.datcore_adapter_settings import DatcoreAdapterSettings

PositiveTimedelta = Annotated[timedelta, Gt(timedelta(0))]


class DsmCleanerSettings(BaseCustomSettings):
    STORAGE_CLEANER_EXPIRE_UPLOADS_INTERVAL: Annotated[
        PositiveTimedelta, Field(description="Interval when task cleaning expired upload links runs.")
    ] = timedelta(minutes=15)

    STORAGE_CLEANER_EXPORT_INTERVAL: Annotated[
        PositiveTimedelta,
        Field(
            description=(
                "Interval when task cleaning expired exporter archives runs. Exports are kept for "
                "STORAGE_CLEANER_EXPORT_RETENTION"
            ),
        ),
    ] = timedelta(hours=6)

    STORAGE_CLEANER_EXPORT_RETENTION: Annotated[
        PositiveTimedelta, Field(description=("Amount of time an exported archive (exports/ S3 prefix) is kept for"))
    ] = timedelta(days=30)


class ApplicationSettings(BaseApplicationSettings, MixinLoggingSettings):
    STORAGE_HOST: str = "0.0.0.0"  # nosec  # noqa: S104
    STORAGE_PORT: PortInt = 8080

    LOG_LEVEL: Annotated[
        LogLevel,
        Field(
            validation_alias=AliasChoices("STORAGE_LOGLEVEL", "LOG_LEVEL", "LOGLEVEL"),
        ),
    ] = LogLevel.INFO

    STORAGE_MONITORING_ENABLED: bool = False
    STORAGE_PROFILING: bool = False

    STORAGE_POSTGRES: Annotated[
        PostgresSettings | None,
        Field(json_schema_extra={"auto_default_from_env": True}),
    ]

    STORAGE_RABBITMQ: Annotated[RabbitSettings, Field(json_schema_extra={"auto_default_from_env": True})]

    STORAGE_REDIS: Annotated[RedisSettings, Field(json_schema_extra={"auto_default_from_env": True})]

    STORAGE_S3: Annotated[S3Settings | None, Field(json_schema_extra={"auto_default_from_env": True})]

    STORAGE_CELERY: Annotated[CelerySettings | None, Field(json_schema_extra={"auto_default_from_env": True})]

    STORAGE_TRACING: Annotated[TracingSettings | None, Field(json_schema_extra={"auto_default_from_env": True})]

    DATCORE_ADAPTER: Annotated[DatcoreAdapterSettings, Field(json_schema_extra={"auto_default_from_env": True})]

    STORAGE_SYNC_METADATA_TIMEOUT: Annotated[
        PositiveInt, Field(180, description="Timeout (seconds) for metadata sync task")
    ]

    STORAGE_DEFAULT_PRESIGNED_LINK_EXPIRATION_SECONDS: Annotated[
        int,
        Field(3600, description="Default expiration time in seconds for presigned links"),
    ]

    STORAGE_CLEANER: Annotated[DsmCleanerSettings, Field(json_schema_extra={"auto_default_from_env": True})]

    STORAGE_S3_CLIENT_MAX_TRANSFER_CONCURRENCY: Annotated[
        int,
        Field(
            4,
            description="Maximal amount of threads used by underlying S3 client to transfer data to S3 backend",
        ),
    ]

    STORAGE_LOG_FORMAT_LOCAL_DEV_ENABLED: Annotated[
        bool,
        Field(
            default=False,
            validation_alias=AliasChoices(
                "STORAGE_LOG_FORMAT_LOCAL_DEV_ENABLED",
                "LOG_FORMAT_LOCAL_DEV_ENABLED",
            ),
            description=(
                "Enables local development _logger format. WARNING: make sure it is disabled "
                "if you want to have structured logs!"
            ),
        ),
    ]

    STORAGE_LOG_FILTER_MAPPING: Annotated[
        dict[LoggerName, list[MessageSubstring]],
        Field(
            default_factory=dict,
            validation_alias=AliasChoices("STORAGE_LOG_FILTER_MAPPING", "LOG_FILTER_MAPPING"),
            description=(
                "is a dictionary that maps specific loggers (such as 'uvicorn.access' or 'gunicorn.access') "
                "to a list of _logger message patterns that should be filtered out."
            ),
        ),
    ]

    STORAGE_BOOT_SERVER_MODE: Annotated[
        BootServerMode,
        Field(description="Boot mode: REST API server or Celery worker"),
    ] = BootServerMode.AS_REST_API_SERVER

    @field_validator("LOG_LEVEL", mode="before")
    @classmethod
    def _validate_loglevel(cls, value: str) -> str:
        log_level: str = cls.validate_log_level(value)
        return log_level


def get_application_settings(app: FastAPI) -> ApplicationSettings:
    assert isinstance(app.state.settings, ApplicationSettings)  # nosec
    return app.state.settings
