# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

from pathlib import Path

import pytest


def pytest_addoption(parser: pytest.Parser):
    parser.addoption(
        "--service-under-test-dir", help="Root directory of the service under test"
    )


@pytest.fixture
def service_under_test_dir(pytestconfig: pytest.Config) -> Path:
    """Base directory of the service under test (--service-under-test-dir)"""
    try:
        dir_path = Path(pytestconfig.getoption("--service-under-test-dir"))
    except TypeError:
        pytest.fail("Invalid path --service-under-test-dir")
    assert dir_path.exists()
    return dir_path
