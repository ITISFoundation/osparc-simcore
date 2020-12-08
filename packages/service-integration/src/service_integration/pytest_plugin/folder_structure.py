# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import sys
from pathlib import Path
from typing import Tuple

import pytest

current_dir = Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent


@pytest.fixture(scope="session")
def project_slug_dir() -> Path:
    raise NotImplementedError("Override fixture 'project_slug_dir' REQUIRED")


@pytest.fixture(scope="session")
def project_name(project_slug_dir) -> str:
    # Override if it does not apply
    return project_slug_dir.name


@pytest.fixture(scope="session")
def src_dir(project_slug_dir: Path) -> Path:
    _src_dir = project_slug_dir / "src"
    assert _src_dir.exists()
    return _src_dir


@pytest.fixture(scope="session")
def tests_dir(project_slug_dir) -> Path:
    _tests_dir = project_slug_dir / "tests"
    assert _tests_dir.exists()
    return _tests_dir


@pytest.fixture(scope="session")
def validation_dir(project_slug_dir: Path) -> Path:
    validation_dir = project_slug_dir / "validation"
    assert validation_dir.exists()
    return validation_dir


@pytest.fixture(scope="session")
def tools_dir(project_slug_dir: Path) -> Path:
    tools_dir = project_slug_dir / "tools"
    assert tools_dir.exists()
    return tools_dir


@pytest.fixture(scope="session")
def docker_dir(project_slug_dir: Path) -> Path:
    docker_dir = project_slug_dir / "docker"
    assert docker_dir.exists()
    return docker_dir


@pytest.fixture(scope="session")
def metadata_file(project_slug_dir: Path) -> Path:
    metadata_file = project_slug_dir / "metadata" / "metadata.yml"
    assert metadata_file.exists()
    return metadata_file


# HELPERS -----------


def get_expected_files(docker_name: str) -> Tuple[str, ...]:
    return (
        ".cookiecutterrc",
        ".dockerignore",
        ".gitignore",
        ".pylintrc",
        "metadata:metadata.yml",
        f"docker/{docker_name}:entrypoint.sh",
        f"docker/{docker_name}:Dockerfile",
        "service.cli:execute.sh",
        "versioning:integration.cfg",
        "versioning:service.cfg",
        "requirements.in",
        "requirements.txt",
        "Makefile",
        "VERSION",
        "VERSION_INTEGRATION",
        "README.md",
        "docker-compose-build.yml",
        "docker-compose-meta.yml",
        "docker-compose.devel.yml",
        "docker-compose.yml",
    )


def assert_path_in_repo(expected_path: str, project_slug_dir: Path):

    if ":" in expected_path:
        folder, glob = expected_path.split(":")
        folder_path = project_slug_dir / folder
        assert folder_path.exists(), f"folder {folder_path} is missing!"
        assert any(folder_path.glob(glob)), f"no {glob} in {folder_path}"
    else:
        assert (
            project_slug_dir / expected_path
        ).exists(), f"{expected_path} is missing from {project_slug_dir}"
