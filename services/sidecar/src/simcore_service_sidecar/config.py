import logging
import multiprocessing
import os
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
