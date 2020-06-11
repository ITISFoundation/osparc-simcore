# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import sys
from pathlib import Path

import pytest

import simcore_service_api_server

current_dir = Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent


@pytest.fixture(scope="session")
def project_slug_dir():
    folder = current_dir.parent.parent
    assert folder.exists()
    assert any(folder.glob("src/simcore_service_api_server"))
    return folder


@pytest.fixture(scope="session")
def package_dir():
    dirpath = Path(simcore_service_api_server.__file__).resolve().parent
    assert dirpath.exists()
    return dirpath


@pytest.fixture(scope="session")
def osparc_simcore_root_dir(project_slug_dir):
    root_dir = project_slug_dir.parent.parent
    assert (
        root_dir and root_dir.exists()
    ), "Did you renamed or moved the integration folder under api-server??"
    assert any(root_dir.glob("services/api-server")), (
        "%s not look like rootdir" % root_dir
    )
    return root_dir


@pytest.fixture(scope="session")
def tests_dir() -> Path:
    tdir = (current_dir / ".." ).resolve()
    assert tdir.exists()
    assert tdir.name == "tests"
    return tdir


@pytest.fixture(scope="session")
def tests_utils_dir(tests_dir: Path) -> Path:
    utils_dir = (tests_dir / "utils").resolve()
    assert utils_dir.exists()
    return utils_dir
