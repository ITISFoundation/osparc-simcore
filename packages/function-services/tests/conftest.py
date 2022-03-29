# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-import
from pathlib import Path

import pytest
import simcore_function_services

pytest_plugins = [
    "pytest_simcore.repository_paths",
    "pytest_simcore.schemas",
    "pytest_simcore.pydantic_models",
    "pytest_simcore.pytest_global_environs",
]


@pytest.fixture(scope="session")
def package_dir() -> Path:
    pdir = Path(simcore_function_services.__file__).resolve().parent
    assert pdir.exists()
    return pdir
