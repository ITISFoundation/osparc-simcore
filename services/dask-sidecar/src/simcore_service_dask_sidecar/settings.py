from pathlib import Path
from typing import Optional

from pydantic import Field, NonNegativeInt
from settings_library.base import BaseCustomSettings
from simcore_service_sidecar import config


class Settings(BaseCustomSettings):
    SC_BUILD_TARGET: Optional[str] = None
    SC_BOOT_MODE: Optional[str] = None

    SWARM_STACK_NAME: str = "simcore"

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

    # dask config ----

    DASK_CLUSTER_ID_PREFIX: Optional[str] = Field(
        "CLUSTER_", description="This defines the cluster name prefix"
    )

    DASK_DEFAULT_CLUSTER_ID: Optional[NonNegativeInt] = Field(
        0, description="This defines the default cluster id when none is defined"
    )

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

    @classmethod
    def create_from_envs(cls) -> "Settings":
        return cls()
