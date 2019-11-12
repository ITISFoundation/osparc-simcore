# pylint: disable=unused-argument
# pylint: disable=bare-except
# pylint:disable=redefined-outer-name

import json
import logging
import sys
from pathlib import Path
from typing import Dict

import pytest

## current directory
current_dir = Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent

## Log
log = logging.getLogger(__name__)


@pytest.fixture(scope='session')
def here():
    cdir = Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent
    assert cdir == current_dir, "Somebody changing current_dir?"
    return cdir

@pytest.fixture(scope='session')
def mock_dir() -> Path:
    dirpath = current_dir / "mock"
    assert dirpath.exists()
    return dirpath

@pytest.fixture
def fake_project(fake_data_dir: Path) -> Dict:
    with (fake_data_dir / "fake-project.json").open() as fp:
        yield json.load(fp)

@pytest.fixture
def project_schema_file(api_specs_dir: Path) -> Path:
    return api_specs_dir / "v0/components/schemas/project-v0.0.1.json"
