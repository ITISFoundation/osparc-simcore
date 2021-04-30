# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import sys
from pathlib import Path

import pytest
import simcore_service_sidecar

pytest_plugins = [
    "pytest_simcore.docker_compose",
    "pytest_simcore.docker_swarm",
    "pytest_simcore.monkeypatch_extra",
    "pytest_simcore.postgres_service",
    "pytest_simcore.rabbit_service",
    "pytest_simcore.repository_paths",
]

current_dir = Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent


@pytest.fixture(scope="session")
def project_slug_dir() -> Path:
    folder = current_dir.parent
    assert folder.exists()
    assert any(folder.glob("src/simcore_service_sidecar"))
    return folder


@pytest.fixture(scope="session")
def package_dir() -> Path:
    dirpath = Path(simcore_service_sidecar.__file__).resolve().parent
    assert dirpath.exists()
    return dirpath
