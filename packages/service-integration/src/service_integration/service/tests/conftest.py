# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

from pathlib import Path

import pytest

pytest_plugins = [
    #     "service_integration.pytest_plugin.folder_structure",
    #     "service_integration.pytest_plugin.validation_data",
    #     "service_integration.pytest_plugin.docker_integration",
]


def pytest_addoption(parser: pytest.Parser):
    parser.addoption(
        "--service-under-test-dir", help="Root directory of the service under test"
    )


@pytest.fixture
def service_under_test_dir(pytestconfig: pytest.Config) -> Path:
    """Base directory of the service under test (--service-under-test-dir)"""
    dir_path = pytestconfig.getoption("--service-under-test-dir")
    assert dir_path
    dir_path = Path(dir_path)
    assert dir_path.exists()
    return dir_path
