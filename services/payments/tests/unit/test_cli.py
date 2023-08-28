# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

import os

from pytest import MonkeyPatch
from pytest_simcore.helpers.typing_env import EnvVarsDict
from pytest_simcore.helpers.utils_envs import load_dotenv, setenvs_from_dict
from simcore_service_payments._meta import API_VERSION
from simcore_service_payments.cli import app
from simcore_service_payments.core.settings import ApplicationSettings
from typer.testing import CliRunner


def test_cli_help_and_version(cli_runner: CliRunner):
    # payments-maker --help
    result = cli_runner.invoke(app, "--help")
    assert result.exit_code == os.EX_OK, result.output

    result = cli_runner.invoke(app, "--version")
    assert result.exit_code == os.EX_OK, result.output
    assert result.stdout.strip() == API_VERSION


def test_generate_dotenv(cli_runner: CliRunner, monkeypatch: MonkeyPatch):
    # payments-maker --generate-dotenv
    result = cli_runner.invoke(app, "generate-dotenv --auto-password")
    assert result.exit_code == os.EX_OK, result.output

    environs = load_dotenv(result.stdout)

    envs = setenvs_from_dict(monkeypatch, environs)
    settings_from_obj = ApplicationSettings.parse_obj(envs)
    settings_from_envs = ApplicationSettings()

    assert settings_from_envs == settings_from_obj


def test_list_settings(cli_runner: CliRunner, app_environment: EnvVarsDict):
    result = cli_runner.invoke(app, ["settings", "--show-secrets", "--as-json"])
    assert result.exit_code == os.EX_OK, result.output

    print(result.output)
    settings = ApplicationSettings.parse_raw(result.output)
    assert settings == ApplicationSettings.create_from_envs()
