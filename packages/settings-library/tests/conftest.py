# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-import

import sys
from pathlib import Path
from typing import Dict, Type, Union

import pytest
import settings_library
from dotenv import dotenv_values
from pydantic import Field
from settings_library.base import BaseCustomSettings
from settings_library.basic_types import PortInt
from settings_library.postgres import PostgresSettings

pytest_plugins = [
    "pytest_simcore.cli_runner",
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


@pytest.fixture
def env_file():
    """Name of env file under tests/mocks folder. Override to change default"""
    return ".env-sample"


@pytest.fixture
def mock_environment(
    mocks_folder: Path, monkeypatch, env_file: str
) -> Dict[str, Union[str, None]]:
    env_file_path = mocks_folder / env_file
    assert env_file_path.exists()
    envs = dotenv_values(str(env_file_path))

    for name, value in envs.items():
        monkeypatch.setenv(name, value)

    return envs


@pytest.fixture
def settings_cls() -> Type[BaseCustomSettings]:
    """Creates a fake Settings class

    NOTE: Add mock_environment fixture before instanciating this class
    """

    class MyModuleSettings(BaseCustomSettings):
        """Settings for Module 1"""

        MYMODULE_VALUE: int = Field(..., description="Some value for module 1")

    class AnotherModuleSettings(BaseCustomSettings):
        """Settings for Module 2"""

        MYMODULE2_SOME_OTHER_VALUE: int

    class Settings(BaseCustomSettings):
        """The App Settings"""

        APP_HOST: str
        APP_PORT: PortInt = 3

        APP_POSTGRES: PostgresSettings
        APP_MODULE_1: MyModuleSettings = Field(..., description="Some Module Example")
        APP_MODULE_2: AnotherModuleSettings

    return Settings
