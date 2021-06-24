from pathlib import Path
from typing import Optional

import simcore_service_sidecar.config as config
from models_library.settings.base import BaseCustomSettings
from models_library.settings.celery import CeleryConfig
from pydantic import Field


class Settings(BaseCustomSettings):
    SC_BUILD_TARGET: Optional[str] = None
    SC_BOOT_MODE: Optional[str] = None

    # sidecar config ---

    SIDECAR_INPUT_FOLDER: Path = config.SIDECAR_INPUT_FOLDER
    SIDECAR_OUTPUT_FOLDER: Path = config.SIDECAR_OUTPUT_FOLDER
    SIDECAR_LOG_FOLDER: Path = config.SIDECAR_LOG_FOLDER

    SIDECAR_DOCKER_VOLUME_INPUT: str = config.SIDECAR_DOCKER_VOLUME_INPUT
    SIDECAR_DOCKER_VOLUME_OUTPUT: str = config.SIDECAR_DOCKER_VOLUME_OUTPUT
    SIDECAR_DOCKER_VOLUME_LOG: str = config.SIDECAR_DOCKER_VOLUME_LOG

    SIDECAR_HOST_HOSTNAME_PATH: Path = config.SIDECAR_HOST_HOSTNAME_PATH
    SIDECAR_INTERVAL_TO_CHECK_TASK_ABORTED_S: int = (
        config.SIDECAR_INTERVAL_TO_CHECK_TASK_ABORTED_S
    )

    FORCE_START_CPU_MODE: bool = config.FORCE_START_CPU_MODE
    FORCE_START_GPU_MODE: bool = config.FORCE_START_GPU_MODE

    TARGET_MPI_NODE_CPU_COUNT: int = Field(
        config.TARGET_MPI_NODE_CPU_COUNT,
        description="If a node has this amount of CPUs it will be a candidate an MPI candidate",
    )

    REDLOCK_REFRESH_INTERVAL_SECONDS: float = Field(
        config.REDLOCK_REFRESH_INTERVAL_SECONDS,
        description="Used by the mpi lock to ensure the lock is acquired and released in time. Enforce at least 1 sec",
    )

    CELERY: Optional[CeleryConfig] = config.CELERY_CONFIG

    # dask config ----

    DASK_SCHEDULER_ADDRESS: Optional[str] = Field(
        None,
        description="Address of the scheduler to register (only if started as worker )",
    )

    def as_scheduler(self) -> bool:
        return self.DASK_SCHEDULER_ADDRESS is None

    def as_worker(self) -> bool:
        return not self.as_scheduler()

    @classmethod
    def create_from_envs(cls) -> "Settings":
        return cls()
