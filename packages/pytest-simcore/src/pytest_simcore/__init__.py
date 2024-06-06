# Collection of tests fixtures for integration testing
from importlib.metadata import version
from pathlib import Path

import pytest

__version__: str = version("pytest-simcore")


def pytest_addoption(parser: pytest.Parser):
    simcore_group = parser.getgroup("simcore", description="pytest-simcore options")
    simcore_group.addoption(
        "--keep-docker-up",
        action="store_true",
        default=False,
        help="Keep stack/registry up after fixtures closes",
    )

    # DUMMY
    parser.addini("HELLO", "Dummy pytest.ini setting")


@pytest.fixture
def is_pdb_enabled(request: pytest.FixtureRequest):
    """Returns true if tests are set to use interactive debugger, i.e. --pdb"""
    options = request.config.option
    return options.usepdb
