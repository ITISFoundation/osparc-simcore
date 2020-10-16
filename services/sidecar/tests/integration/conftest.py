# pylint: disable=redefined-outer-name
import logging
import sys
from pathlib import Path

import pytest
from simcore_service_sidecar.boot_mode import BootMode, set_boot_mode

current_dir = Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent

# imports the fixtures for the integration tests
pytest_plugins = [
    "pytest_simcore.repository_paths",
    "pytest_simcore.schemas",
    "pytest_simcore.docker_compose",
    "pytest_simcore.docker_swarm",
    "pytest_simcore.docker_registry",
    "pytest_simcore.rabbit_service",
    "pytest_simcore.postgres_service",
    "pytest_simcore.minio_service",
    "pytest_simcore.simcore_storage_service",
]
log = logging.getLogger(__name__)


@pytest.fixture(scope="session")
def mock_dir() -> Path:
    folder = current_dir / "mock"
    assert folder.exists()
    return folder


@pytest.fixture(scope="session")
def python_sample_script(mock_dir: Path) -> Path:
    file_path = mock_dir / "osparc_python_sample.py"
    assert file_path.exists()
    return file_path


@pytest.fixture()
def mock_boot_mode():
    """by default only CPU is mocked which is enough"""
    set_boot_mode(BootMode.CPU)
