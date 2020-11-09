# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name


import sys
from pathlib import Path

current_dir = Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent
pytest_plugins = [
    "pytest_simcore.docker_compose",
    "pytest_simcore.docker_registry",
    "pytest_simcore.docker_swarm",
    "pytest_simcore.repository_paths",
    "pytest_simcore.postgres_service",
    "pytest_simcore.rabbit_service",
    "pytest_simcore.redis_service",
    "pytest_simcore.schemas",
    "pytest_simcore.simcore_services",
]
