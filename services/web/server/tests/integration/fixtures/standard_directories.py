# pylint:disable=wildcard-import
# pylint:disable=unused-import
# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

# FIXME: overlaps of these fixtures with those in tests/unit/conftest.py


import sys
from pathlib import Path

import pytest
import simcore_service_webserver

current_dir =  Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent


@pytest.fixture(scope='session')
def fixture_dir() -> Path:
    return current_dir

@pytest.fixture(scope='session')
def package_dir() -> Path:
    dirpath = Path(simcore_service_webserver.__file__).resolve().parent
    assert dirpath.exists()
    return dirpath

@pytest.fixture(scope='session')
def osparc_simcore_root_dir(fixture_dir: Path) -> Path:
    """
        NOTE: This fixture will only work if folders under version control (i.e. contain '.git' folder)
    """
    root_dir = fixture_dir.resolve()
    while not any(root_dir.glob(".git")) and root_dir != Path("/"):
        root_dir = root_dir.parent

    assert root_dir.exists(), "Is this service within osparc-simcore repo?"
    assert any(root_dir.glob("services/web/server")), f"'{root_dir}' does not look like the git root directory of osparc-simcore"
    return root_dir

@pytest.fixture(scope='session')
def api_specs_dir(osparc_simcore_root_dir: Path) -> Path:
    specs_dir = osparc_simcore_root_dir/ "api" / "specs" / "webserver"
    assert specs_dir.exists()
    return specs_dir

@pytest.fixture(scope='session')
def integration_test_dir(fixture_dir: Path) -> Path:
    tests_dir = fixture_dir.parent.resolve()
    assert tests_dir.exists()
    return tests_dir

@pytest.fixture(scope='session')
def tests_dir(integration_test_dir: Path) -> Path:
    tests_dir = integration_test_dir.parent.resolve()
    assert tests_dir.exists()
    return tests_dir

@pytest.fixture(scope='session')
def fake_data_dir(tests_dir: Path) -> Path:
    fake_data_dir = tests_dir / "data"
    assert fake_data_dir.exists()
    return fake_data_dir

@pytest.fixture(scope="session")
def server_test_configfile(mock_dir):
    fpath = mock_dir / "configs/server-host-test.yaml"
    assert fpath.exists()
    return fpath

@pytest.fixture(scope="session")
def light_test_configfile(mock_dir):
    fpath = mock_dir / "configs/light-test.yaml"
    assert fpath.exists()
    return fpath

@pytest.fixture("session")
def env_devel_file(osparc_simcore_root_dir) -> Path:
    env_devel_fpath = osparc_simcore_root_dir / ".env-devel"
    assert env_devel_fpath.exists()
    return env_devel_fpath
