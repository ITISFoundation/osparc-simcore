# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-import
from pathlib import Path

import aws_library
import pytest

pytest_plugins = [
    "pytest_simcore.aws_ec2_service",
    "pytest_simcore.aws_s3_service",
    "pytest_simcore.aws_server",
    "pytest_simcore.environment_configs",
    "pytest_simcore.pydantic_models",
    "pytest_simcore.pytest_global_environs",
    "pytest_simcore.repository_paths",
]


@pytest.fixture(scope="session")
def package_dir() -> Path:
    pdir = Path(aws_library.__file__).resolve().parent
    assert pdir.exists()
    return pdir
