from pathlib import Path
from typing import Optional

from pydantic import Field, NonNegativeInt
from settings_library.base import BaseCustomSettings


class Settings(BaseCustomSettings):
    SC_BUILD_TARGET: Optional[str] = None
    SC_BOOT_MODE: Optional[str] = None

    SWARM_STACK_NAME: str = "simcore"

    # sidecar config ---

    SIDECAR_COMP_SERVICES_SHARED_VOLUME_NAME: str

    SIDECAR_HOST_HOSTNAME_PATH: Path
    SIDECAR_INTERVAL_TO_CHECK_TASK_ABORTED_S: int

    FORCE_START_CPU_MODE: bool
    FORCE_START_GPU_MODE: bool

    TARGET_MPI_NODE_CPU_COUNT: int = Field(
        ...,
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
