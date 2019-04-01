import sys
from pathlib import Path

import pytest

import simcore_service_webserver


@pytest.fixture(scope='session')
def fixture_dir():
    return Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent

@pytest.fixture(scope='session')
def package_dir():
    dirpath = Path(simcore_service_webserver.__file__).resolve().parent
    assert dirpath.exists()
    return dirpath

@pytest.fixture(scope='session')
def osparc_simcore_root_dir(fixture_dir):
    root_dir = fixture_dir.parent.parent.parent.parent.parent.parent.resolve()
    assert root_dir.exists(), "Is this service within osparc-simcore repo?"
    assert any(root_dir.glob("services/web/server")), "%s not look like rootdir" % root_dir
    return root_dir

@pytest.fixture(scope='session')
def api_specs_dir(osparc_simcore_root_dir):
    specs_dir = osparc_simcore_root_dir/ "api" / "specs" / "webserver"
    assert specs_dir.exists()
    return specs_dir

@pytest.fixture(scope='session')
def integration_test_dir(fixture_dir):
    tests_dir = fixture_dir.parent.resolve()
    assert tests_dir.exists()
    return tests_dir

# @pytest.fixture(scope='session')
# def mock_dir(fixture_dir):
#     dirpath = fixture_dir / "mock"
#     assert dirpath.exists()
#     return dirpath

# @pytest.fixture(scope='session')
# def docker_compose_file(mock_dir):
#     """
#       Path to docker-compose configuration files used for testing

#       - fixture defined in pytest-docker
#     """
#     fpath = mock_dir / 'docker-compose.yml'
#     assert fpath.exists()
#     return str(fpath)

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
