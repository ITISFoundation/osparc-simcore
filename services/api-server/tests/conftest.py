# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import sys
from copy import deepcopy
from pathlib import Path

import pytest
import simcore_service_api_server
from dotenv import dotenv_values
from pytest_simcore.helpers.utils_envs import EnvVarsDict, setenvs_from_dict

CURRENT_DIR = Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent


pytest_plugins = [
    "pytest_simcore.pydantic_models",
    "pytest_simcore.pytest_global_environs",
    "pytest_simcore.repository_paths",
]


## TEST_ENVIRON ---


@pytest.fixture(scope="session")
def project_env_devel_vars(project_slug_dir: Path) -> EnvVarsDict:
    env_devel_file = project_slug_dir / ".env-devel"
    assert env_devel_file.exists()
    environ = dotenv_values(env_devel_file, verbose=True, interpolate=True)
    return environ


@pytest.fixture
def patched_project_env_devel_vars(
    project_env_devel_vars: EnvVarsDict, monkeypatch: pytest.MonkeyPatch
) -> None:

    env_vars = deepcopy(project_env_devel_vars)
    # overrides
    env_vars["API_SERVER_DEV_FEATURES_ENABLED"] = "1"

    setenvs_from_dict(monkeypatch, env_vars)
    return env_vars


## FOLDER LAYOUT ----


@pytest.fixture(scope="session")
def project_slug_dir() -> Path:
    folder = CURRENT_DIR.parent
    assert folder.exists()
    assert any(folder.glob("src/simcore_service_api_server"))
    return folder


@pytest.fixture(scope="session")
def package_dir() -> Path:
    """Notice that this might be under src (if installed as edit mode)
    or in the installation folder
    """
    dirpath = Path(simcore_service_api_server.__file__).resolve().parent
    assert dirpath.exists()
    return dirpath


@pytest.fixture(scope="session")
def tests_utils_dir(project_tests_dir: Path) -> Path:
    utils_dir = (project_tests_dir / "utils").resolve()
    assert utils_dir.exists()
    return utils_dir
