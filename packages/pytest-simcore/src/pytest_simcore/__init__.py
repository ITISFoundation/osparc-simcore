# Collection of tests fixtures for integration testing
from importlib.metadata import version

import pytest

__version__: str = version("pytest-simcore")


def pytest_addoption(parser):
    group = parser.getgroup("simcore")
    group.addoption(
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
