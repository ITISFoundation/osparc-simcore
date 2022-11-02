# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
from pathlib import Path

import pytest


@pytest.fixture(scope="session")
def project_slug_dir(request: pytest.FixtureRequest) -> Path:
    try:
        root_dir = Path(request.config.getoption("--service-dir"))
    except TypeError:
        pytest.fail("--service-dir is not set")

    assert isinstance(root_dir, Path)
    assert root_dir.exists()
    assert any(root_dir.glob(".osparc"))
    return root_dir


@pytest.fixture(scope="session")
def project_name(project_slug_dir: Path) -> str:
    # Override if it does not apply
    return project_slug_dir.name


@pytest.fixture(scope="session")
def validation_dir(project_slug_dir: Path) -> Path:
    validation_dir = project_slug_dir / "validation"
    assert validation_dir.exists()
    return validation_dir


@pytest.fixture(scope="session")
def metadata_file(project_slug_dir: Path, request: pytest.FixtureRequest) -> Path:
    try:
        metadata_file = Path(request.config.getoption("--metadata"))
    except TypeError:
        metadata_file = project_slug_dir / "metadata" / "metadata.yml"

    assert isinstance(metadata_file, Path)
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
