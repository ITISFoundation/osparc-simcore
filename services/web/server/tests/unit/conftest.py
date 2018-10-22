# pylint: disable=unused-argument
# pylint: disable=unused-import
# pylint: disable=bare-except
# pylint: disable=W0621

import collections
import logging
import os
import sys
from pathlib import Path

import pytest
import yaml

import init_db
import simcore_service_webserver
from simcore_service_webserver.cli_config import read_and_validate

log = logging.getLogger(__name__)

@pytest.fixture(scope='session')
def here():
    return Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent

@pytest.fixture(scope='session')
def package_dir(here):
    dirpath = Path(simcore_service_webserver.__file__).resolve().parent
    assert dirpath.exists()
    return dirpath

@pytest.fixture(scope='session')
def osparc_simcore_root_dir(here):
    root_dir = here.parent.parent.parent.parent
    assert root_dir.exists(), "Is this service within osparc-simcore repo?"
    return root_dir

@pytest.fixture(scope='session')
def package_paths(pytestconfig, here):
    # Intentionally not using resource paths so we have an alternative
    # way to retrieve paths to test resource logic itself
    package_root = here.parent
    src_folder = package_root / "src"
    test_folder = package_root / "tests"
    mock_folder = test_folder / "mock"

    paths={}
    paths["ROOT_FOLDER"] = package_root
    paths["SRC_FOLDER"] = src_folder
    paths["PACKAGE_FOLDER"] = src_folder / simcore_service_webserver.__name__
    paths["TEST_FOLDER"] = test_folder
    paths["MOCK_FOLDER"] = mock_folder

    for key, path in paths.items():
        assert path.exists(), "Invalid path in %s" % key

    return collections.namedtuple("PackagePaths", paths.keys())(**paths)

@pytest.fixture(scope='session')
def docker_compose_file(package_paths):
    """
      Path to docker-compose configuration files used for testing

      - fixture defined in pytest-docker
    """
    fpath = package_paths.MOCK_FOLDER / 'docker-compose.yml'
    assert fpath.exists()
    return str(fpath)

@pytest.fixture(scope="session")
def server_test_configfile(package_paths):
    fpath = package_paths.MOCK_FOLDER / "configs/server-host-test.yaml"
    assert fpath.exists()
    return fpath

@pytest.fixture(scope="session")
def light_test_configfile(package_paths):
    fpath = package_paths.MOCK_FOLDER / "configs/light-test.yaml"
    assert fpath.exists()
    return fpath
