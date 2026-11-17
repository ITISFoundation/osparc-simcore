# pylint: disable=redefined-outer-name
#
# Fixture to test Typer applications
#
# SEE https://typer.tiangolo.com/tutorial/testing/#testing-input
# Based on https://github.com/Stranger6667/pytest-click


from collections.abc import Iterator
from pathlib import Path

import pytest
from typer.testing import CliRunner


@pytest.fixture
def cli_runner() -> CliRunner:
    """Instance of `typer.testing.CliRunner`"""
    return CliRunner()


@pytest.fixture
def isolated_cli_runner(cli_runner: CliRunner, tmp_path: Path) -> Iterator[CliRunner]:
    """Instance of `typer.testing.CliRunner` running under a temporary working
    directory for isolated filesystem tests.
    """
    with pytest.MonkeyPatch.context() as mp:
        mp.chdir(tmp_path)
        yield cli_runner
