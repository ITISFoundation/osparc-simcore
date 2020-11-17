# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

from pathlib import Path

import pytest

expected_files = (
    ".cookiecutterrc",
    ".dockerignore",
    ".gitignore",
    ".pylintrc",
    "metadata:metadata.yml",
    "docker/{{ cookiecutter.docker_base.split(":")[0] }}:entrypoint.sh",
    "docker/{{ cookiecutter.docker_base.split(":")[0] }}:Dockerfile",
    "service.cli:execute.sh",
    "tools:run_creator.py",
    "tools:update_compose_labels.py",
    "versioning:integration.cfg",
    "versioning:service.cfg",
    "requirements.in",
    "requirements.txt",
    "Makefile",
    "VERSION",
    "README.md",
    "docker-compose-build.yml",
    "docker-compose-meta.yml",
    "docker-compose.devel.yml",
    "docker-compose.yml",
)


@pytest.mark.parametrize("expected_path", expected_files)
def test_path_in_repo(expected_path: str, project_slug_dir: Path):

    if ":" in expected_path:
        folder, glob = expected_path.split(":")
        folder_path = project_slug_dir / folder
        assert folder_path.exists(), f"folder {folder_path} is missing!"
        assert any(folder_path.glob(glob)), f"no {glob} in {folder_path}"
    else:
        assert (project_slug_dir/expected_path).exists(
        ), f"{expected_path} is missing from {project_slug_dir}"
