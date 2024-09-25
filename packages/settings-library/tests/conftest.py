# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-import

import sys
from pathlib import Path

import pytest
import settings_library
from dotenv import dotenv_values
from pydantic.fields import Field
from pytest_simcore.helpers.typing_env import EnvVarsDict
from settings_library.base import BaseCustomSettings
from settings_library.basic_types import PortInt
from settings_library.postgres import PostgresSettings

pytest_plugins = [
    "pytest_simcore.cli_runner",
    "pytest_simcore.environment_configs",
    "pytest_simcore.pydantic_models",
    "pytest_simcore.pytest_global_environs",
    "pytest_simcore.repository_paths",
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
def project_tests_data_folder(project_tests_dir: Path) -> Path:
    dir_path = project_tests_dir / "data"
    assert dir_path.exists()
    return dir_path


@pytest.fixture
def env_file():
    """Name of env file under tests/mocks folder. Override to change default"""
    return ".env-sample"


@pytest.fixture
def mock_environment(
    project_tests_data_folder: Path, monkeypatch, env_file: str
) -> EnvVarsDict:
    """mocks environment provided in the env_file"""
    env_file_path = project_tests_data_folder / env_file
    assert env_file_path.exists()

    envs = dotenv_values(str(env_file_path))

    for name, value in envs.items():
        monkeypatch.setenv(name, value)

    return envs


@pytest.fixture
def fake_settings_class() -> type[BaseCustomSettings]:
    """Creates a fake Settings class

    NOTE: How to use this fixture? BaseCustomSettings captures env vars, therefore
          make sure the environment is well defined(e.g. add always some monkeypatch based
          fixture as 'mock_environment') before this fixture.
    """
    # Some conventions:
    # NOTE: all int defaults are 42, i.e. the "Answer to the Ultimate Question of Life, the Universe, and Everything"
    # NOTE: suffixes are used to distinguis different options on the same field (e.g. _OPTIONAL, etc)

    class _ModuleSettings(BaseCustomSettings):
        """Settings for a Module"""

        MODULE_VALUE: int
        MODULE_VALUE_DEFAULT: int = 42

    class _ApplicationSettings(BaseCustomSettings):
        """The main app settings"""

        # Some flat field config
        APP_HOST: str
        APP_PORT: PortInt = 42

        # NOTE: by convention, an addon is disabled when APP_ADDON=None, so we make this
        # entry nullable as well
        APP_OPTIONAL_ADDON: _ModuleSettings | None = Field(
            json_schema_extra={"auto_default_from_env": True}
        )

        # NOTE: example of a group that cannot be disabled (not nullable)
        APP_REQUIRED_PLUGIN: PostgresSettings | None = Field(
            json_schema_extra={"auto_default_from_env": True}
        )

    return _ApplicationSettings
