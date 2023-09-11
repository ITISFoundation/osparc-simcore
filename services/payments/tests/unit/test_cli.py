# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

import os

import pytest
from pytest_simcore.helpers.typing_env import EnvVarsDict
from pytest_simcore.helpers.utils_envs import load_dotenv, setenvs_from_dict
from simcore_service_payments._meta import API_VERSION
from simcore_service_payments.cli import main as cli_main
from simcore_service_payments.core.settings import ApplicationSettings
from typer.testing import CliRunner


def test_cli_help_and_version(cli_runner: CliRunner):
    # simcore-service-payments --help
    result = cli_runner.invoke(cli_main, "--help")
    assert result.exit_code == os.EX_OK, result.output

    result = cli_runner.invoke(cli_main, "--version")
    assert result.exit_code == os.EX_OK, result.output
    assert result.stdout.strip() == API_VERSION


def test_generate_dotenv(cli_runner: CliRunner, monkeypatch: pytest.MonkeyPatch):
    # simcore-service-payments generate-dotenv --auto-password
    result = cli_runner.invoke(cli_main, "generate-dotenv --auto-password")
    assert result.exit_code == os.EX_OK, result.output

    environs = load_dotenv(result.stdout)

    with monkeypatch.context() as patch:
        envs = setenvs_from_dict(patch, environs)
        settings_from_obj = ApplicationSettings.parse_obj(envs)
        settings_from_envs = ApplicationSettings.create_from_envs()

        assert settings_from_envs == settings_from_obj


def test_list_settings(cli_runner: CliRunner, app_environment: EnvVarsDict):
    # simcore-service-payments settings --show-secrets --as-json
    result = cli_runner.invoke(cli_main, ["settings", "--show-secrets", "--as-json"])
    assert result.exit_code == os.EX_OK, result.output

    print(result.output)
    settings = ApplicationSettings.parse_raw(result.output)
    assert settings == ApplicationSettings.create_from_envs()


def test_main(app_environment: EnvVarsDict):
    from simcore_service_payments.main import the_app

    assert the_app
