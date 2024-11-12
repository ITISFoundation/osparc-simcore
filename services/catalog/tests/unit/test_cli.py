# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import os

from pytest_simcore.helpers.typing_env import EnvVarsDict
from simcore_service_catalog._meta import API_VERSION
from simcore_service_catalog.cli import main
from simcore_service_catalog.core.settings import ApplicationSettings
from typer.testing import CliRunner


def test_cli_help_and_version(cli_runner: CliRunner):
    result = cli_runner.invoke(main, "--help")
    assert result.exit_code == os.EX_OK, result.output

    result = cli_runner.invoke(main, "--version")
    assert result.exit_code == os.EX_OK, result.output
    assert result.stdout.strip() == API_VERSION


def test_settings(cli_runner: CliRunner, app_environment: EnvVarsDict):
    result = cli_runner.invoke(main, ["settings", "--show-secrets", "--as-json"])
    assert result.exit_code == os.EX_OK

    print(result.output)
    settings = ApplicationSettings(result.output)
    assert settings.model_dump() == ApplicationSettings.create_from_envs().model_dump()


def test_run(cli_runner: CliRunner):
    result = cli_runner.invoke(main, ["run"])
    assert result.exit_code == 0
    assert "disabled" in result.stdout
