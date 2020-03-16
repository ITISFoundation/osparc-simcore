import logging
import multiprocessing
import os


SERVICES_MAX_NANO_CPUS: int = min(
    multiprocessing.cpu_count() * pow(10,9),
    int(os.environ.get("SIDECAR_SERVICES_MAX_NANO_CPUS", 4 * pow(10, 9))),
)
SERVICES_MAX_MEMORY_BYTES: int = os.environ.get(
    "SIDECAR_SERVICES_MAX_MEMORY_BYTES", 2 * pow(1024, 3)
)
SERVICES_TIMEOUT_SECONDS: int = os.environ.get("SIDECAR_SERVICES_TIMEOUT_SECONDS", 20 * 60)
SWARM_STACK_NAME: str = os.environ.get("SWARM_STACK_NAME", "simcore")

SIDECAR_LOGLEVEL: str = getattr(
    logging, os.environ.get("SIDECAR_LOGLEVEL", "WARNING").upper(), logging.WARNING
)

logging.basicConfig(level=SIDECAR_LOGLEVEL)
logging.getLogger("sqlalchemy.engine").setLevel(SIDECAR_LOGLEVEL)
logging.getLogger("sqlalchemy.pool").setLevel(SIDECAR_LOGLEVEL)
