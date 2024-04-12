# Collection of tests fixtures for integration testing
from importlib.metadata import version
from pathlib import Path

import pytest

__version__: str = version("pytest-simcore")


def pytest_addoption(parser):
    simcore_group = parser.getgroup(
        "simcore", description="options related to pytest simcore"
    )
    simcore_group.addoption(
        "--keep-docker-up",
        action="store_true",
        default=False,
        help="Keep stack/registry up after fixtures closes",
    )

    simcore_group.addoption(
        "--external-envfile",
        action="store",
        type=Path,
        default=None,
        help="Path to an env file. Consider passing a link to repo configs, i.e. `ln -s /path/to/osparc-ops-config/repo.config`",
    )

    # DUMMY
    parser.addini("HELLO", "Dummy pytest.ini setting")


@pytest.fixture
def is_pdb_enabled(request: pytest.FixtureRequest):
    """Returns true if tests are set to use interactive debugger, i.e. --pdb"""
    options = request.config.option
    return options.usepdb
