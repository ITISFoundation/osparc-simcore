from pathlib import Path
from typing import Annotated, Any

from models_library.basic_types import LogLevel
from pydantic import AliasChoices, Field, field_validator
from servicelib.logging_utils_filtering import LoggerName, MessageSubstring
from settings_library.base import BaseCustomSettings
from settings_library.utils_logging import MixinLoggingSettings


class Settings(BaseCustomSettings, MixinLoggingSettings):
    """Dask-sidecar app settings"""

    SC_BUILD_TARGET: str | None = None
    SC_BOOT_MODE: str | None = None
    LOG_LEVEL: Annotated[
        LogLevel,
        Field(
            LogLevel.INFO.value,
            validation_alias=AliasChoices(
                "DASK_SIDECAR_LOGLEVEL", "SIDECAR_LOGLEVEL", "LOG_LEVEL", "LOGLEVEL"
            ),
        ),
    ]

    # sidecar config ---

    SIDECAR_COMP_SERVICES_SHARED_VOLUME_NAME: str
    SIDECAR_COMP_SERVICES_SHARED_FOLDER: Path

    SIDECAR_INTERVAL_TO_CHECK_TASK_ABORTED_S: int | None = 5

    # dask config ----

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

    def as_scheduler(self) -> bool:
        return bool(self.DASK_START_AS_SCHEDULER)

    def as_worker(self) -> bool:
        as_worker = not self.as_scheduler()
        if as_worker:
            assert self.DASK_SCHEDULER_HOST is not None  # nosec
        return as_worker

    @field_validator("LOG_LEVEL", mode="before")
    @classmethod
    def _validate_loglevel(cls, value: Any) -> str:
        return cls.validate_log_level(f"{value}")
