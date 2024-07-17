# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-import

import shutil
import sys
from collections.abc import Callable
from pathlib import Path

import pytest
import service_integration
from service_integration import cli
from typer.testing import CliRunner

pytest_plugins = [
    "pytest_simcore.pydantic_models",
    "pytest_simcore.pytest_global_environs",
    "pytest_simcore.repository_paths",
]

_CURRENT_DIR = (
    Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent
)


@pytest.fixture(scope="session")
def package_dir() -> Path:
    pdir = Path(service_integration.__file__).resolve().parent
    assert pdir.exists()
    return pdir


@pytest.fixture(scope="session")
def tests_data_dir() -> Path:
    pdir = _CURRENT_DIR / "data"
    assert pdir.exists()
    return pdir


@pytest.fixture
def docker_compose_overwrite_path(tests_data_dir, tmp_path) -> Path:
    name = "docker-compose.overwrite.yml"
    dst = shutil.copy(
        src=tests_data_dir / name,
        dst=tmp_path / name,
    )
    return Path(dst)


@pytest.fixture
def metadata_file_path(tests_data_dir, tmp_path) -> Path:
    name = "metadata.yml"
    dst = shutil.copy(
        src=tests_data_dir / name,
        dst=tmp_path / name,
    )
    return Path(dst)


@pytest.fixture
def run_program_with_args() -> Callable:
    # SEE https://click.palletsprojects.com/en/7.x/testing/
    runner = CliRunner()

    def _invoke(*cmd):
        print("RUNNING", "simcore-service-integrator", cmd)
        print(runner.make_env())
        return runner.invoke(cli.app, list(cmd))

    return _invoke
