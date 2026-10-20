# pylint: disable=redefined-outer-name
#
# Fixture to test Typer applications
#
# SEE https://typer.tiangolo.com/tutorial/testing/#testing-input
# Based on https://github.com/Stranger6667/pytest-click


import shutil
from collections.abc import Iterator
from pathlib import Path

import pytest
from typer.testing import CliRunner


@pytest.fixture
def cli_runner() -> CliRunner:
    """Instance of `typer.testing.CliRunner`"""
    return CliRunner()


@pytest.fixture
def isolated_cli_runner(cli_runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[CliRunner]:
    """Instance of `typer.testing.CliRunner` running under a temporary working
    directory for isolated filesystem tests.
    """
    monkeypatch.chdir(tmp_path)
    try:
        yield cli_runner
    finally:
        monkeypatch.undo()
        shutil.rmtree(tmp_path, ignore_errors=True)
