import logging
import multiprocessing
import os
from pathlib import Path
from typing import Optional

from simcore_sdk.config.rabbit import Config as RabbitConfig

SERVICES_MAX_NANO_CPUS: int = min(
    multiprocessing.cpu_count() * pow(10, 9),
    int(os.environ.get("SIDECAR_SERVICES_MAX_NANO_CPUS", 4 * pow(10, 9))),
)
SERVICES_MAX_MEMORY_BYTES: int = int(
    os.environ.get("SIDECAR_SERVICES_MAX_MEMORY_BYTES", 2 * pow(1024, 3))
)
SERVICES_TIMEOUT_SECONDS: int = int(
    os.environ.get("SIDECAR_SERVICES_TIMEOUT_SECONDS", 20 * 60)
)
SWARM_STACK_NAME: str = os.environ.get("SWARM_STACK_NAME", "simcore")

SIDECAR_INPUT_FOLDER: Path = Path(
    os.environ.get("SIDECAR_INPUT_FOLDER", Path.home() / "input")
)
SIDECAR_OUTPUT_FOLDER: Path = Path(
    os.environ.get("SIDECAR_OUTPUT_FOLDER", Path.home() / "output")
)
SIDECAR_LOG_FOLDER: Path = Path(
    os.environ.get("SIDECAR_LOG_FOLDER", Path.home() / "log")
)

SIDECAR_DOCKER_VOLUME_INPUT: str = os.environ.get(
    "SIDECAR_DOCKER_VOLUME_INPUT", f"{SWARM_STACK_NAME}_input"
)
SIDECAR_DOCKER_VOLUME_OUTPUT: str = os.environ.get(
    "SIDECAR_DOCKER_VOLUME_OUTPUT", f"{SWARM_STACK_NAME}_output"
)
SIDECAR_DOCKER_VOLUME_LOG: str = os.environ.get(
    "SIDECAR_DOCKER_VOLUME_LOG", f"{SWARM_STACK_NAME}_log"
)
SIDECAR_LOGLEVEL: str = getattr(
    logging, os.environ.get("SIDECAR_LOGLEVEL", "WARNING").upper(), logging.WARNING
)

DOCKER_REGISTRY: str = os.environ.get("REGISTRY_URL", "masu.speag.com")
DOCKER_USER: str = os.environ.get("REGISTRY_USER", "z43")
DOCKER_PASSWORD: str = os.environ.get("REGISTRY_PW", "z43")

POSTGRES_ENDPOINT: str = os.environ.get("POSTGRES_ENDPOINT", "postgres:5432")
POSTGRES_DB: str = os.environ.get("POSTGRES_DB", "simcoredb")
POSTGRES_PW: str = os.environ.get("POSTGRES_PASSWORD", "simcore")
POSTGRES_USER: str = os.environ.get("POSTGRES_USER", "simcore")

logging.basicConfig(level=SIDECAR_LOGLEVEL)
logging.getLogger("sqlalchemy.engine").setLevel(SIDECAR_LOGLEVEL)
logging.getLogger("sqlalchemy.pool").setLevel(SIDECAR_LOGLEVEL)

RABBIT_CONFIG = RabbitConfig()
# sidecar celery starting mode overwrite
FORCE_START_CPU_MODE: Optional[str] = os.environ.get("START_AS_MODE_CPU")
FORCE_START_GPU_MODE: Optional[str] = os.environ.get("START_AS_MODE_GPU")

# if a node has this amount of CPUs it will be a candidate an MPI candidate
TARGET_MPI_NODE_CPU_COUNT: int = int(os.environ.get("TARGET_MPI_NODE_CPU_COUNT", "-1"))

# Redis configuration
REDIS_CONNECTION_STRING: str = "redis://{host}:{password}/0".format(
    host=os.environ.get("REDIS_HOST", "redis"),
    password=os.environ.get("REDIS_PORT", "6379"),
)
# used by the mpi lock to ensure the lock is acquired and released in time
REDLOCK_REFRESH_INTERVAL_SECONDS: float = max(
    float(os.environ.get("REDLOCK_REFRESH_INTERVAL_SECONDS", "5.0")), 1.0
)  # enforce at least 1 second
