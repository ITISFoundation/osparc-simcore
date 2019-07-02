# pylint: disable=unused-argument
# pylint: disable=unused-import
# pylint: disable=bare-except
# pylint:disable=redefined-outer-name

import collections
import json
import logging
import os
import sys
from pathlib import Path
from typing import Dict

import pytest
import yaml

import simcore_service_webserver
from simcore_service_webserver.cli_config import read_and_validate

log = logging.getLogger(__name__)

sys.path.append(str(Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent.parent / 'helpers'))

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
    root_dir = here.parent.parent.parent.parent.parent.resolve()
    assert root_dir.exists(), "Is this service within osparc-simcore repo?"
    assert any(root_dir.glob("services/web/server")), "%s not look like rootdir" % root_dir
    return root_dir

@pytest.fixture(scope='session')
def api_specs_dir(osparc_simcore_root_dir):
    specs_dir = osparc_simcore_root_dir/ "api" / "specs" / "webserver"
    assert specs_dir.exists()
    return specs_dir

@pytest.fixture(scope='session')
def mock_dir(here):
    dirpath = here / "mock"
    assert dirpath.exists()
    return dirpath

@pytest.fixture(scope='session')
def fake_data_dir(here):
    dirpath = (here / "../data").resolve()
    assert dirpath.exists()
    return dirpath

@pytest.fixture(scope='session')
def docker_compose_file(mock_dir):
    """
      Path to docker-compose configuration files used for testing

      - fixture defined in pytest-docker
    """
    fpath = mock_dir / 'docker-compose.yml'
    assert fpath.exists()
    return str(fpath)

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

@pytest.fixture
def fake_project(fake_data_dir: Path) -> Dict:
    with (fake_data_dir / "fake-project.json").open() as fp:
        yield json.load(fp)


@pytest.fixture
def project_schema_file(api_specs_dir: Path) -> Path:
    return api_specs_dir / "v0/components/schemas/project-v0.0.1.json"
