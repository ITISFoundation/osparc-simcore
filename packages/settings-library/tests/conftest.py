# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-import

import sys
from pathlib import Path
from typing import Dict, Union

import pytest
import settings_library
from dotenv import dotenv_values

pytest_plugins = [
    "pytest_simcore.repository_paths",
    "pytest_simcore.pydantic_models",
]

CURRENT_DIR = Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent


@pytest.fixture(scope="session")
def package_dir():
    pdir = Path(settings_library.__file__).resolve().parent
    assert pdir.exists()
    return pdir


@pytest.fixture(scope="session")
def project_slug_dir() -> Path:
    folder = CURRENT_DIR.parent
    assert folder.exists()
    assert any(folder.glob("src/settings_library"))
    return folder


@pytest.fixture(scope="session")
def mocks_folder(project_tests_dir: Path) -> Path:
    dir_path = project_tests_dir / "mocks"
    assert dir_path.exists()
    return dir_path


@pytest.fixture(scope="function")
def mock_environment(
    env_file: str, mocks_folder: Path, monkeypatch
) -> Dict[str, Union[str, None]]:
    env_file_path = mocks_folder / env_file
    assert env_file_path.exists()
    envs = dotenv_values(str(env_file_path))

    for name, value in envs.items():
        monkeypatch.setenv(name, value)

    return envs
