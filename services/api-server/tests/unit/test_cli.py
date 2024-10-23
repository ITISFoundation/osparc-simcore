# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


import os

from fastapi import FastAPI
from pytest_simcore.helpers.typing_env import EnvVarsDict
from simcore_service_api_server.cli import main
from simcore_service_api_server.core.settings import ApplicationSettings
from typer.testing import CliRunner


def test_cli_help(cli_runner: CliRunner):
    result = cli_runner.invoke(main, "--help")
    assert result.exit_code == os.EX_OK, result.output


def test_cli_run(cli_runner: CliRunner):
    result = cli_runner.invoke(main, "run")
    assert "disabled" in result.output
    assert result.exit_code == os.EX_OK, result.output


def test_cli_list_settings(cli_runner: CliRunner, app_environment: EnvVarsDict):
    result = cli_runner.invoke(main, ["settings", "--show-secrets", "--as-json"])
    assert result.exit_code == os.EX_OK, result.output

    print(result.output)
    settings = ApplicationSettings.model_validate_json(result.output)
    assert settings == ApplicationSettings.create_from_envs()


def test_main(app_environment: EnvVarsDict):
    from simcore_service_api_server.main import the_app

    assert the_app
    assert isinstance(the_app, FastAPI)
