""" Main test configuration

    EXPECTED: simcore_service_webserver installed

"""
# pylint: disable=unused-argument
# pylint: disable=bare-except
# pylint: disable=redefined-outer-name

import logging
import sys
from pathlib import Path
from typing import Dict

import pytest

import simcore_service_webserver

from integration.utils import get_fake_data_dir, get_fake_project

current_dir = Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent

log = logging.getLogger(__name__)

# mute noisy loggers
logging.getLogger("openapi_spec_validator").setLevel(logging.WARNING)
logging.getLogger("sqlalchemy").setLevel(logging.WARNING)


@pytest.fixture(scope="session")
def package_dir() -> Path:
    """ osparc-simcore installed directory """
    dirpath = Path(simcore_service_webserver.__file__).resolve().parent
    assert dirpath.exists()
    return dirpath


@pytest.fixture(scope="session")
def api_specs_dir(osparc_simcore_root_dir: Path) -> Path:
    specs_dir = osparc_simcore_root_dir / "api" / "specs" / "webserver"
    assert specs_dir.exists()
    return specs_dir


@pytest.fixture(scope="session")
def fake_data_dir() -> Path:
    fake_data_dir = get_fake_data_dir()
    assert fake_data_dir.exists()
    return fake_data_dir


@pytest.fixture
def fake_project(fake_data_dir: Path) -> Dict:
    return get_fake_project()
