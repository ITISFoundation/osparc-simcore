from datetime import timedelta
from typing import Annotated, Self

from common_library.basic_types import DEFAULT_FACTORY
from common_library.logging.logging_utils_filtering import LoggerName, MessageSubstring
from common_library.pydantic_validators import validate_numeric_string_as_timedelta
from fastapi import FastAPI
from pydantic import AliasChoices, Field, PositiveInt, field_validator, model_validator
from settings_library.application import BaseApplicationSettings
from settings_library.basic_types import LogLevel, PortInt
from settings_library.celery import CelerySettings
from settings_library.postgres import PostgresSettings
from settings_library.rabbit import RabbitSettings
from settings_library.redis import RedisSettings
from settings_library.s3 import S3Settings
from settings_library.tracing import TracingSettings
from settings_library.utils_logging import MixinLoggingSettings

from ..modules.datcore_adapter.datcore_adapter_settings import DatcoreAdapterSettings


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
        PositiveInt, Field(description="Timeout (seconds) for metadata sync task")
    ] = 180

    STORAGE_DEFAULT_PRESIGNED_LINK_EXPIRATION_SECONDS: Annotated[
        int,
        Field(description="Default expiration time in seconds for presigned links"),
    ] = 3600

    STORAGE_CLEANER_INTERVAL_S: Annotated[
        int | None,
        Field(
            description=(
                "Interval in seconds when task cleaning pending uploads runs. setting to NULL disables the cleaner."
            ),
        ),
    ] = 30

    STORAGE_CLEANER_RECONCILE_ENABLED: Annotated[
        bool,
        Field(
            description=(
                "Master switch for the reconciliation janitor."
                " The pass runs incrementally and crash-resumable from Redis cursor state."
            ),
        ),
    ] = False

    STORAGE_CLEANER_RECONCILE_INTERVAL: Annotated[
        timedelta,
        Field(
            description=(
                "Minimum interval (seconds) between reconciliation ticks."
                " This is independent of STORAGE_CLEANER_INTERVAL_S so upload-expiry cleanup"
                " can still run frequently while reconciliation progresses at a gentler cadence."
            ),
        ),
    ] = timedelta(minutes=5)

    STORAGE_CLEANER_RECONCILE_GRACE_PERIOD: Annotated[
        timedelta,
        Field(
            description=(
                "Minimum age before a candidate is considered for reconciliation deletion."
                " Must be >= STORAGE_DEFAULT_PRESIGNED_LINK_EXPIRATION_SECONDS to avoid"
                " deleting fmd rows whose uploads are still in flight (the computational"
                " backend may upload for up to the full presigned-URL lifetime)."
            ),
        ),
    ] = timedelta(days=30)

    STORAGE_CLEANER_RECONCILE_SCAN_BATCH_SIZE: Annotated[
        PositiveInt,
        Field(
            description=("Maximum number of fmd rows processed per incremental reconciliation tick."),
        ),
    ] = 1200

    STORAGE_S3_CLIENT_MAX_TRANSFER_CONCURRENCY: Annotated[
        int,
        Field(
            description="Maximal amount of threads used by underlying S3 client to transfer data to S3 backend",
        ),
    ] = 4

    STORAGE_LOG_FORMAT_LOCAL_DEV_ENABLED: Annotated[
        bool,
        Field(
            validation_alias=AliasChoices(
                "STORAGE_LOG_FORMAT_LOCAL_DEV_ENABLED",
                "LOG_FORMAT_LOCAL_DEV_ENABLED",
            ),
            description=(
                "Enables local development _logger format. WARNING: make sure it is disabled "
                "if you want to have structured logs!"
            ),
        ),
    ] = False

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
    ] = DEFAULT_FACTORY

    STORAGE_WORKER_MODE: Annotated[bool, Field(description="If True, run as a worker")] = False

    @field_validator("LOG_LEVEL", mode="before")
    @classmethod
    def _validate_loglevel(cls, value: str) -> str:
        log_level: str = cls.validate_log_level(value)
        return log_level

    @model_validator(mode="after")
    def _ensure_settings_consistency(self) -> Self:
        if self.STORAGE_CLEANER_INTERVAL_S is not None and not self.STORAGE_REDIS:
            msg = "STORAGE_CLEANER_INTERVAL_S cleaner cannot be set without STORAGE_REDIS! Please correct settings."
            raise ValueError(msg)

        min_grace = timedelta(seconds=self.STORAGE_DEFAULT_PRESIGNED_LINK_EXPIRATION_SECONDS)
        if min_grace > self.STORAGE_CLEANER_RECONCILE_GRACE_PERIOD:
            msg = (
                f"STORAGE_CLEANER_RECONCILE_GRACE_PERIOD ({self.STORAGE_CLEANER_RECONCILE_GRACE_PERIOD})"
                f" must be >= STORAGE_DEFAULT_PRESIGNED_LINK_EXPIRATION_SECONDS ({min_grace})."
                " A shorter grace period risks deleting fmd rows for uploads still in flight."
            )
            raise ValueError(msg)

        return self

    _validate_storage_cleaner_reconcile_interval = validate_numeric_string_as_timedelta(
        "STORAGE_CLEANER_RECONCILE_INTERVAL"
    )
    _validate_storage_cleaner_reconcile_grace_period = validate_numeric_string_as_timedelta(
        "STORAGE_CLEANER_RECONCILE_GRACE_PERIOD"
    )


def get_application_settings(app: FastAPI) -> ApplicationSettings:
    assert isinstance(app.state.settings, ApplicationSettings)  # nosec
    return app.state.settings
