# pylint: disable=unused-argument
# pylint: disable=bare-except
# pylint:disable=redefined-outer-name

import json
import logging
import sys
from pathlib import Path
from typing import Dict

import pytest

import simcore_service_webserver


## current directory
current_dir = Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent

## Log
log = logging.getLogger(__name__)
# mute noisy loggers
logging.getLogger("openapi_spec_validator").setLevel(logging.WARNING)
logging.getLogger("sqlalchemy").setLevel(logging.WARNING)

## include test/helpers
sys.path.append(str(current_dir.parent / 'helpers'))



@pytest.fixture(scope='session')
def here():
    cdir = Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent
    assert cdir == current_dir, "Somebody changing current_dir?"
    return cdir


@pytest.fixture(scope='session')
def package_dir():
    # FIXME: use services/web/server/tests/integration/fixtures/standard_directories.py
    dirpath = Path(simcore_service_webserver.__file__).resolve().parent
    assert dirpath.exists()
    return dirpath

@pytest.fixture(scope='session')
def osparc_simcore_root_dir():
    # FIXME: use services/web/server/tests/integration/fixtures/standard_directories.py
    root_dir = current_dir.parent.parent.parent.parent.parent.resolve()
    assert root_dir.exists(), "Is this service within osparc-simcore repo?"
    assert any(root_dir.glob("services/web/server")), "%s not look like rootdir" % root_dir
    return root_dir

@pytest.fixture(scope='session')
def api_specs_dir(osparc_simcore_root_dir):
    # FIXME: use services/web/server/tests/integration/fixtures/standard_directories.py
    specs_dir = osparc_simcore_root_dir/ "api" / "specs" / "webserver"
    assert specs_dir.exists()
    return specs_dir

@pytest.fixture(scope='session')
def mock_dir():
    dirpath = current_dir / "mock"
    assert dirpath.exists()
    return dirpath

@pytest.fixture(scope='session')
def fake_data_dir():
    dirpath = (current_dir / "../data").resolve()
    assert dirpath.exists()
    return dirpath

@pytest.fixture
def fake_project(fake_data_dir: Path) -> Dict:
    with (fake_data_dir / "fake-project.json").open() as fp:
        yield json.load(fp)

@pytest.fixture
def project_schema_file(api_specs_dir: Path) -> Path:
    return api_specs_dir / "v0/components/schemas/project-v0.0.1.json"
