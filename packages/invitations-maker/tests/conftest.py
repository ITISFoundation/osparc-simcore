# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments
import pytest
from cryptography.fernet import Fernet

pytest_plugins = [
    "pytest_simcore.cli_runner",
]


@pytest.fixture
def secret_key() -> str:
    key = Fernet.generate_key()
    return key.decode()
