from pathlib import Path
from typing import Annotated, Any

from models_library.basic_types import LogLevel
from pydantic import AliasChoices, Field, field_validator
from servicelib.logging_utils_filtering import LoggerName, MessageSubstring
from settings_library.application import BaseApplicationSettings
from settings_library.utils_logging import MixinLoggingSettings


class ApplicationSettings(BaseApplicationSettings, MixinLoggingSettings):
    DASK_SIDECAR_LOGLEVEL: Annotated[
        LogLevel,
        Field(
            validation_alias=AliasChoices(
                "DASK_SIDECAR_LOGLEVEL", "SIDECAR_LOGLEVEL", "LOG_LEVEL", "LOGLEVEL"
            ),
        ),
    ] = LogLevel.INFO

    SIDECAR_COMP_SERVICES_SHARED_VOLUME_NAME: str
    SIDECAR_COMP_SERVICES_SHARED_FOLDER: Path

    DASK_SIDECAR_INTERVAL_TO_CHECK_TASK_ABORTED_S: int | None = 5

    DASK_START_AS_SCHEDULER: bool | None = Field(
        default=False, description="If this env is set, then the app boots as scheduler"
    )

    DASK_SCHEDULER_HOST: str | None = Field(
        None,
        description="Address of the scheduler to register (only if started as worker )",
    )

    DASK_LOG_FORMAT_LOCAL_DEV_ENABLED: bool = Field(
        default=False,
        validation_alias=AliasChoices(
            "DASK_LOG_FORMAT_LOCAL_DEV_ENABLED",
            "LOG_FORMAT_LOCAL_DEV_ENABLED",
        ),
        description="Enables local development log format. WARNING: make sure it is disabled if you want to have structured logs!",
    )
    DASK_LOG_FILTER_MAPPING: dict[LoggerName, list[MessageSubstring]] = Field(
        default_factory=dict,
        validation_alias=AliasChoices("DASK_LOG_FILTER_MAPPING", "LOG_FILTER_MAPPING"),
        description="is a dictionary that maps specific loggers (such as 'uvicorn.access' or 'gunicorn.access') to a list of log message patterns that should be filtered out.",
    )

    @field_validator("DASK_SIDECAR_LOGLEVEL", mode="before")
    @classmethod
    def _validate_loglevel(cls, value: Any) -> str:
        return cls.validate_log_level(f"{value}")
