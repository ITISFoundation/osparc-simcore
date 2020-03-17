import logging
import sys
from pathlib import Path

current_dir = Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent
# TODO: this should be done as a real pytest plugin instead
sys.path.append(str(current_dir / "../../../../packages"))
# imports the fixtures for the integration tests
pytest_plugins = [
    "pytest-fixtures.environs",
    "pytest-fixtures.docker_compose",
    "pytest-fixtures.docker_swarm",
    "pytest-fixtures.docker_registry",
    "pytest-fixtures.rabbit_service",
    "pytest-fixtures.postgres_service",
    "pytest-fixtures.minio_service",
    "pytest-fixtures.simcore_storage_service",
]
log = logging.getLogger(__name__)
