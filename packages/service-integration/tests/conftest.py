# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-import
import shutil
import sys
from pathlib import Path
from typing import Callable

import pytest
import service_integration
from click.testing import CliRunner
from service_integration.cli import main

pytest_plugins = [
    "pytester",
    "pytest_simcore.repository_paths",
    "pytest_simcore.schemas",
]

current_dir = Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent


@pytest.fixture(scope="session")
def package_dir() -> Path:
    pdir = Path(service_integration.__file__).resolve().parent
    assert pdir.exists()
    return pdir


@pytest.fixture(scope="session")
def tests_data_dir() -> Path:
    pdir = current_dir / "data"
    assert pdir.exists()
    return pdir


@pytest.fixture
def metadata_file_path(tests_data_dir, tmp_path) -> Path:
    dst = shutil.copy(
        src=tests_data_dir / "metadata.yml", dst=tmp_path / "metadata.yml"
    )
    return Path(dst)


@pytest.fixture
def run_simcore_service_integrator() -> Callable:
    # SEE https://click.palletsprojects.com/en/7.x/testing/
    runner = CliRunner()

    def _invoke(*cmd):
        print("RUNNING", "simcore-service-integrator", cmd)
        return runner.invoke(main, list(cmd))

    return _invoke
