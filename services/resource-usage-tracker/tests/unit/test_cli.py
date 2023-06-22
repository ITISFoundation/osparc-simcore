# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

import os

import requests_mock
from pytest_simcore.helpers.typing_env import EnvVarsDict
from simcore_service_resource_usage_tracker._meta import API_VERSION
from simcore_service_resource_usage_tracker.cli import app
from simcore_service_resource_usage_tracker.core.settings import ApplicationSettings
from typer.testing import CliRunner


def test_cli_help_and_version(cli_runner: CliRunner):
    result = cli_runner.invoke(app, "--help")
    assert result.exit_code == os.EX_OK, result.output

    result = cli_runner.invoke(app, "--version")
    assert result.exit_code == os.EX_OK, result.output
    assert result.stdout.strip() == API_VERSION


def test_list_settings(cli_runner: CliRunner, app_environment: EnvVarsDict):
    result = cli_runner.invoke(app, ["settings", "--show-secrets", "--as-json"])
    assert result.exit_code == os.EX_OK, result.output

    print(result.output)
    settings = ApplicationSettings.parse_raw(result.output)
    assert settings == ApplicationSettings.create_from_envs()


def test_evaluate_without_configuration_raises(
    cli_runner: CliRunner,
):
    result = cli_runner.invoke(app, ["evaluate", "1234"])
    assert result.exit_code == 1, result.output


def test_evaluate(
    cli_runner: CliRunner,
    app_environment: EnvVarsDict,
    mocked_prometheus_with_query: requests_mock.Mocker,
):
    result = cli_runner.invoke(app, ["evaluate", "43817"])
    assert result.exit_code == os.EX_OK, result.output
