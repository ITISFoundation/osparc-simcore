from pathlib import Path
from typing import Any, cast

from models_library.basic_types import LogLevel
from pydantic import Field, validator
from settings_library.base import BaseCustomSettings
from settings_library.utils_logging import MixinLoggingSettings


class Settings(BaseCustomSettings, MixinLoggingSettings):
    """Dask-sidecar app settings"""

    SC_BUILD_TARGET: str | None = None
    SC_BOOT_MODE: str | None = None
    LOG_LEVEL: LogLevel = Field(
        LogLevel.INFO.value,
        env=["DASK_SIDECAR_LOGLEVEL", "SIDECAR_LOGLEVEL", "LOG_LEVEL", "LOGLEVEL"],
    )

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
        env=["DASK_LOG_FORMAT_LOCAL_DEV_ENABLED", "LOG_FORMAT_LOCAL_DEV_ENABLED"],
        description="Enables local development log format. WARNING: make sure it is disabled if you want to have structured logs!",
    )

    def as_scheduler(self) -> bool:
        return bool(self.DASK_START_AS_SCHEDULER)

    def as_worker(self) -> bool:
        as_worker = not self.as_scheduler()
        if as_worker:
            assert self.DASK_SCHEDULER_HOST is not None  # nosec
        return as_worker

    @validator("LOG_LEVEL", pre=True)
    @classmethod
    def _validate_loglevel(cls, value: Any) -> str:
        return cast(str, cls.validate_log_level(f"{value}"))
