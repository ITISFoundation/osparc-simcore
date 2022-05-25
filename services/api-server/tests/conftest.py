# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import sys
from pathlib import Path

import pytest
import simcore_service_api_server
from cryptography.fernet import Fernet
from dotenv import dotenv_values
from pytest_simcore.helpers.utils_envs import EnvVarsDict

CURRENT_DIR = Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent


pytest_plugins = [
    "pytest_simcore.pydantic_models",
    "pytest_simcore.pytest_global_environs",
    "pytest_simcore.repository_paths",
]


## TEST_ENVIRON ---


@pytest.fixture(scope="session")
def default_test_env_vars() -> dict[str, str]:
    return {
        "WEBSERVER_HOST": "webserver",
        "WEBSERVER_SESSION_SECRET_KEY": Fernet.generate_key().decode("utf-8"),
        "POSTGRES_HOST": "127.0.0.1",
        "POSTGRES_USER": "test",
        "POSTGRES_PASSWORD": "test",
        "POSTGRES_DB": "test",
        "LOG_LEVEL": "debug",
        "SC_BOOT_MODE": "production",
    }


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
    for key, value in project_env_devel_vars.items():
        monkeypatch.setenv(key, value)

    # overrides
    monkeypatch.setenv("API_SERVER_DEV_FEATURES_ENABLED", "1")


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
