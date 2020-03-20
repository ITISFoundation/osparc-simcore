import logging
import sys
from pathlib import Path

current_dir = Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent

# imports the fixtures for the integration tests
pytest_plugins = [
    "pytest_simcore.environs",
    "pytest_simcore.docker_compose",
    "pytest_simcore.docker_swarm",
    "pytest_simcore.docker_registry",
    "pytest_simcore.rabbit_service",
    "pytest_simcore.postgres_service",
    "pytest_simcore.minio_service",
    "pytest_simcore.simcore_storage_service",
]
log = logging.getLogger(__name__)
