from pathlib import Path
from typing import Any, Optional, cast

from models_library.basic_types import LogLevel
from pydantic import Field, validator
from settings_library.base import BaseCustomSettings
from settings_library.utils_logging import MixinLoggingSettings


class Settings(BaseCustomSettings, MixinLoggingSettings):
    SC_BUILD_TARGET: Optional[str] = None
    SC_BOOT_MODE: Optional[str] = None
    LOG_LEVEL: LogLevel = Field(
        LogLevel.INFO.value,
        env=["DASK_SIDECAR_LOGLEVEL", "SIDECAR_LOGLEVEL", "LOG_LEVEL", "LOGLEVEL"],
    )

    # sidecar config ---

    SIDECAR_COMP_SERVICES_SHARED_VOLUME_NAME: str
    SIDECAR_COMP_SERVICES_SHARED_FOLDER: Path

    SIDECAR_INTERVAL_TO_CHECK_TASK_ABORTED_S: Optional[int] = 5

    TARGET_MPI_NODE_CPU_COUNT: Optional[int] = Field(
        None,
        description="If a node has this amount of CPUs it will be a candidate an MPI candidate",
    )

    # dask config ----

    DASK_START_AS_SCHEDULER: Optional[bool] = Field(
        False, description="If this env is set, then the app boots as scheduler"
    )

    DASK_SCHEDULER_HOST: Optional[str] = Field(
        None,
        description="Address of the scheduler to register (only if started as worker )",
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
