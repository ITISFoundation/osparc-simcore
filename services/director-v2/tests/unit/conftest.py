# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import sys
from pathlib import Path
from typing import Dict

import dotenv
import pytest

import simcore_service_director_v2

current_dir = Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent
pytest_plugins = [
    "pytest_simcore.repository_paths",
    "pytest_simcore.environment_configs",
]


@pytest.fixture(scope="session")
def project_slug_dir(services_dir) -> Path:
    # uses pytest_simcore.environs.osparc_simcore_root_dir
    service_folder = services_dir / "director-v2"
    assert service_folder.exists()
    assert any(service_folder.glob("src/simcore_service_director_v2"))
    return service_folder


@pytest.fixture(scope="session")
def project_env_devel_config(project_slug_dir) -> Dict:
    env_path = project_slug_dir / ".env-devel"
    parsed = dotenv.dotenv_values(dotenv_path=env_path)
    return parsed


@pytest.fixture(scope="function")
def env_evel_environ(project_env_devel_config, monkeypatch):
    for key, value in project_env_devel_config.items():
        print(key, "=", value)
        monkeypatch.setenv(key, value)


@pytest.fixture(scope="session")
def installed_package_dir() -> Path:
    dirpath = Path(simcore_service_director_v2.__file__).resolve().parent
    assert dirpath.exists()
    return dirpath
