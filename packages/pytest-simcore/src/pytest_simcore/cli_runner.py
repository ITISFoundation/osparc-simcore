# pylint: disable=redefined-outer-name
#
# Fixture to test Typer applications
#
# SEE https://typer.tiangolo.com/tutorial/testing/#testing-input
# Based on https://github.com/Stranger6667/pytest-click


from collections.abc import Iterator

import pytest
from typer.testing import CliRunner


@pytest.fixture
def cli_runner() -> CliRunner:
    """Instance of `typer.testing.CliRunner`"""
    return CliRunner()


@pytest.fixture
def isolated_cli_runner(cli_runner: CliRunner) -> Iterator[CliRunner]:
    """Instance of `typer.testing.CliRunner` running under a temporary working directory for isolated filesystem tests."""
    with cli_runner.isolated_filesystem():
        yield cli_runner
