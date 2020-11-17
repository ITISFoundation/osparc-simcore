# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import sys
from pathlib import Path

import pytest

current_dir = Path(sys.argv[0] if __name__ ==
                   "__main__" else __file__).resolve().parent


@pytest.fixture(scope='session')
def tests_dir() -> Path:
    assert current_dir.exists()
    return current_dir


@pytest.fixture(scope='session')
def validation_dir(project_slug_dir: Path) -> Path:
    validation_dir = project_slug_dir / "validation"
    assert validation_dir.exists()
    return validation_dir


@pytest.fixture(scope='session')
def project_slug_dir(tests_dir: Path) -> Path:
    project_slug_dir = tests_dir.parent
    assert project_slug_dir.exists()
    return project_slug_dir


@pytest.fixture(scope='session')
def src_dir(project_slug_dir: Path) -> Path:
    src_dir = project_slug_dir / "src"
    assert src_dir.exists()
    return src_dir


@pytest.fixture(scope='session')
def tools_dir(project_slug_dir: Path) -> Path:
    tools_dir = project_slug_dir / "tools"
    assert tools_dir.exists()
    return tools_dir


@pytest.fixture(scope='session')
def docker_dir(project_slug_dir: Path) -> Path:
    docker_dir = project_slug_dir / "docker"
    assert docker_dir.exists()
    return docker_dir


@pytest.fixture(scope='session')
def package_dir(src_dir: Path) -> Path:
    package_dir = src_dir / "name_of_the_project"
    assert package_dir.exists()
    return package_dir

@pytest.fixture(scope='session')
def metadata_file(project_slug_dir: Path) -> Path:
    metadata_file = project_slug_dir / "metadata" / "metadata.yml"
    assert metadata_file.exists()
    return metadata_file

@pytest.fixture(scope='session')
def git_root_dir() -> Path:
    # finds where is .git
    root_dir = current_dir
    while root_dir.as_posix() != "/" and not Path(root_dir / ".git").exists():
        root_dir = root_dir.parent
    if root_dir.as_posix() == "/":
        return None
    return root_dir
