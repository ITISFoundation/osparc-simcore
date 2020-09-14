# pylint: disable=redefined-outer-name
"""these are fixtures for when running unit tests
    """
from pathlib import Path

import pytest
from dotenv import load_dotenv


@pytest.fixture(scope="session")
def service_env_file(project_slug_dir: Path) -> Path:
    env_devel_path = project_slug_dir / ".env-devel"
    assert env_devel_path.exists()
    return env_devel_path


@pytest.fixture(scope="session", autouse=True)
def service_test_environ(service_env_file: Path) -> None:
    """this fixtures overload the environ with unit testing only variables
    """
    load_dotenv(service_env_file, verbose=True)
