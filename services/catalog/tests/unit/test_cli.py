# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import os

from simcore_service_catalog._meta import API_VERSION
from simcore_service_catalog.cli import main
from typer.testing import CliRunner


def test_cli_help_and_version(cli_runner: CliRunner):
    result = cli_runner.invoke(main, "--help")
    assert result.exit_code == os.EX_OK, result.output

    result = cli_runner.invoke(main, "--version")
    assert result.exit_code == os.EX_OK, result.output
    assert result.stdout.strip() == API_VERSION


def test_settings(cli_runner: CliRunner):
    result = cli_runner.invoke(main, ["settings"])
    assert result.exit_code == 0
    assert "APP_NAME=simcore-service-autoscaling" in result.stdout


def test_run(cli_runner: CliRunner):
    result = cli_runner.invoke(main, ["run"])
    assert result.exit_code == 0
    assert "disabled" in result.stdout
