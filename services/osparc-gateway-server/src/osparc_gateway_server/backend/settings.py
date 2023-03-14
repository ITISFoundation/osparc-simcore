from enum import Enum
from typing import Optional

from pydantic import BaseSettings, Field


class BootModeEnum(str, Enum):
    """
    Values taken by SC_BOOT_MODE environment variable
    set in Dockerfile and used during docker/boot.sh
    """

    DEFAULT = "default"
    LOCAL = "local-development"
    DEBUG = "debug-ptvsd"
    PRODUCTION = "production"
    DEVELOPMENT = "development"


class AppSettings(BaseSettings):
    COMPUTATIONAL_SIDECAR_IMAGE: str = Field(
        ..., description="The computational sidecar image in use"
    )
    COMPUTATIONAL_SIDECAR_LOG_LEVEL: Optional[str] = Field(
        "WARNING",
        description="The computational sidecar log level",
        env=[
            "COMPUTATIONAL_SIDECAR_LOG_LEVEL",
            "LOG_LEVEL",
            "LOGLEVEL",
            "SIDECAR_LOG_LEVEL",
            "SIDECAR_LOGLEVEL",
        ],
    )
    COMPUTATIONAL_SIDECAR_VOLUME_NAME: str = Field(
        ..., description="Named volume for the computational sidecars"
    )

    GATEWAY_WORKERS_NETWORK: str = Field(
        ...,
        description="The docker network where the gateway workers shall be able to access the gateway",
    )
    GATEWAY_SERVER_NAME: str = Field(
        ...,
        description="The hostname of the gateway server in the GATEWAY_WORKERS_NETWORK network",
    )

    SC_BOOT_MODE: Optional[BootModeEnum]

    GATEWAY_SERVER_ONE_WORKER_PER_NODE: bool = Field(
        default=True,
        description="Only one dask-worker is allowed per node (default). If disabled, then scaling must be done manually.",
    )

    GATEWAY_CLUSTER_START_TIMEOUT: float = Field(
        default=120.0,
        description="Allowed timeout to define a starting cluster as failed",
    )
    GATEWAY_WORKER_START_TIMEOUT: float = Field(
        default=120.0,
        description="Allowed timeout to define a starting worker as failed",
    )
