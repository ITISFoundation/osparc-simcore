# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import sys
from pathlib import Path

import pytest
import simcore_service_catalog
from pytest_simcore.helpers.typing_env import EnvVarsDict
from pytest_simcore.helpers.utils_envs import load_dotenv, setenvs_from_envfile

pytest_plugins = [
    "pytest_simcore.docker_compose",
    "pytest_simcore.docker_registry",
    "pytest_simcore.docker_swarm",
    "pytest_simcore.monkeypatch_extra",
    "pytest_simcore.postgres_service",
    "pytest_simcore.pydantic_models",
    "pytest_simcore.pytest_global_environs",
    "pytest_simcore.repository_paths",
    "pytest_simcore.schemas",
    "pytest_simcore.tmp_path_extra",
]


_CURRENT_DIR = (
    Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent
)


## FOLDER LAYOUT ---------------------------------------------------------------------


@pytest.fixture(scope="session")
def project_slug_dir() -> Path:
    folder = _CURRENT_DIR.parent.parent
    assert folder.exists()
    assert any(folder.glob("src/simcore_service_catalog"))
    return folder


@pytest.fixture(scope="session")
def package_dir() -> Path:
    """Notice that this might be under src (if installed as edit mode)
    or in the installation folder
    """
    dirpath = Path(simcore_service_catalog.__file__).resolve().parent
    assert dirpath.exists()
    return dirpath


@pytest.fixture(scope="session")
def service_env_file(project_slug_dir: Path) -> Path:
    env_devel_path = project_slug_dir / ".env-devel"
    assert env_devel_path.exists()
    return env_devel_path


# TEST ENVIRONS ------


@pytest.fixture(scope="session")
def testing_environ_vars(
    testing_environ_vars: EnvVarsDict, service_env_file: Path
) -> EnvVarsDict:
    # Extends packages/pytest-simcore/src/pytest_simcore/docker_compose.py::testing_environ_vars
    # Environ seen by docker compose (i.e. postgres_db)
    app_envs = load_dotenv(service_env_file, verbose=True)
    return {**testing_environ_vars, **app_envs}


@pytest.fixture
def service_test_environ(
    service_env_file: Path, monkeypatch: pytest.MonkeyPatch
) -> EnvVarsDict:
    # environs seen by app are defined by the service env-file!
    return setenvs_from_envfile(monkeypatch, service_env_file, verbose=True)
