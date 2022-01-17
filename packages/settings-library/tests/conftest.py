# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-import

import os
import sys
import textwrap
from collections import deque
from contextlib import contextmanager
from pathlib import Path
from typing import Callable, Deque, Generator, Optional, Tuple, Type

import pytest
import settings_library
from _pytest.monkeypatch import MonkeyPatch
from dotenv import dotenv_values
from pydantic import Field
from pytest_simcore.helpers.utils_environs import EnvVarsDict
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
def mock_environment(mocks_folder: Path, monkeypatch, env_file: str) -> EnvVarsDict:

    env_file_path = mocks_folder / env_file
    assert env_file_path.exists()
    envs = dotenv_values(str(env_file_path))

    for name, value in envs.items():
        monkeypatch.setenv(name, value)

    return envs


@pytest.fixture
def fake_settings_class() -> Type[BaseCustomSettings]:
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

        MODULE_VALUE_OPTIONAL: Optional[int]
        MODULE_VALUE_OPTIONAL_ELLIPSES: Optional[int] = ...  # type:ignore
        MODULE_VALUE_OPTIONAL_NONE: Optional[int] = None

        MODULE_VALUE_FIELD: int = Field(..., description="Some value for module 1")
        MODULE_VALUE_DEFAULT: int = 42

    class _AppSettings(BaseCustomSettings):
        """The App Settings"""

        APP_HOST: str
        APP_PORT: PortInt = 42

        # Different options on how to add section settings 'ModuleSettings'
        APP_MODULE: _ModuleSettings

        APP_MODULE_OPTIONAL: Optional[_ModuleSettings]
        APP_MODULE_OPTIONAL_ELLIPSES: Optional[_ModuleSettings] = ...  # type:ignore
        APP_MODULE_OPTIONAL_NONE: Optional[_ModuleSettings] = None

        APP_MODULE_FIELD: _ModuleSettings = Field(
            ..., description="Some value for module 1"
        )

        # Here some real settings
        APP_POSTGRES: PostgresSettings

    return _AppSettings


@pytest.fixture
def mocked_settings_cls_env() -> str:
    # reflects all expected env vars inside the above defined
    # settings_cls fixture
    return """
        APP_HOST=localhost
        APP_PORT=80
        POSTGRES_HOST=localhost
        POSTGRES_PORT=5432
        POSTGRES_USER=foo
        POSTGRES_PASSWORD=**********
        POSTGRES_DB=foodb
        POSTGRES_MINSIZE=1
        POSTGRES_MAXSIZE=50
        POSTGRES_CLIENT_NAME=None
        MYMODULE_VALUE=10
        MYMODULE2_SOME_OTHER_VALUE=33
    """


@pytest.fixture
def mocked_environment(
    monkeypatch: MonkeyPatch,
) -> Callable:
    @contextmanager
    def ctx_mngr(env_formatted_string: str) -> Generator[None, None, None]:
        SAMPLE_ENV = textwrap.dedent(env_formatted_string).strip()
        env_vars: Deque[Tuple[str, str]] = deque()
        for line in SAMPLE_ENV.split("\n"):
            key, value = line.split("=")
            env_vars.append((key, value))

        # ensure env_vars are not already defined
        for key, value in env_vars:
            assert os.environ.get(key, None) is None

        with monkeypatch.context() as m:
            for key, value in env_vars:
                m.setenv(key, value)

            for key, value in env_vars:
                assert os.environ[key] == value

            yield

        # ensure env_vars are not longer present
        for key, value in env_vars:
            assert os.environ.get(key, None) is None

    return ctx_mngr
