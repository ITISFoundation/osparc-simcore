# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-import
from pathlib import Path

import aws_library
import pytest
from settings_library.ec2 import EC2Settings

pytest_plugins = [
    "pytest_simcore.aws_ec2_service",
    "pytest_simcore.aws_s3_service",
    "pytest_simcore.aws_server",
    "pytest_simcore.aws_ssm_service",
    "pytest_simcore.environment_configs",
    "pytest_simcore.file_extra",
    "pytest_simcore.logging",
    "pytest_simcore.pydantic_models",
    "pytest_simcore.pytest_global_environs",
    "pytest_simcore.repository_paths",
]


@pytest.fixture(scope="session")
def package_dir() -> Path:
    pdir = Path(aws_library.__file__).resolve().parent
    assert pdir.exists()
    return pdir


@pytest.fixture
def ec2_settings(mocked_ec2_server_settings: EC2Settings) -> EC2Settings:
    return mocked_ec2_server_settings
