# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
import sys
from pathlib import Path

import pytest

current_dir = Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent


@pytest.fixture(scope="session")
def project_slug_dir() -> Path:
    raise NotImplementedError("Override fixture 'project_slug_dir' REQUIRED")


@pytest.fixture(scope="session")
def project_name(project_slug_dir: Path) -> str:
    # Override if it does not apply
    return project_slug_dir.name


@pytest.fixture(scope="session")
def src_dir(project_slug_dir: Path) -> Path:
    _src_dir = project_slug_dir / "src"
    assert _src_dir.exists()
    return _src_dir


@pytest.fixture(scope="session")
def tests_dir(project_slug_dir: Path) -> Path:
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


def get_expected_files(docker_name: str) -> tuple[str, ...]:
    return (
        ".cookiecutterrc",
        ".dockerignore",
        "metadata:metadata.yml",
        f"docker/{docker_name}:entrypoint.sh",
        f"docker/{docker_name}:Dockerfile",
        "service.cli:execute.sh",
        "docker-compose-build.yml",
        "docker-compose-meta.yml",
        "docker-compose.devel.yml",
        "docker-compose.yml",
    )


def assert_path_in_repo(expected_path: str, project_slug_dir: Path):

    if ":" in expected_path:
        folder, glob_pattern = expected_path.split(":")
        folder_path = project_slug_dir / folder
        assert folder_path.exists(), f"folder '{folder_path}' is missing!"
        assert any(
            folder_path.glob(glob_pattern)
        ), f"no {glob_pattern=} in '{folder_path}'"
    else:
        assert (
            project_slug_dir / expected_path
        ).exists(), f"'{expected_path}' is missing from '{project_slug_dir}'"
