# pylint:disable=unused-argument

import os
import traceback

import pytest
from click.testing import Result
from pytest_simcore.helpers.monkeypatch_envs import load_dotenv, setenvs_from_dict
from pytest_simcore.helpers.typing_env import EnvVarsDict
from simcore_service_dynamic_scheduler._meta import API_VERSION
from simcore_service_dynamic_scheduler.cli import main as cli_main
from simcore_service_dynamic_scheduler.core.settings import ApplicationSettings
from typer.testing import CliRunner


def _format_cli_error(result: Result) -> str:
    assert result.exception
    tb_message = "\n".join(traceback.format_tb(result.exception.__traceback__))
    return f"Below exception was raised by the cli:\n{tb_message}"


def test_cli_help_and_version(cli_runner: CliRunner):
    # simcore-service-dynamic-scheduler --help
    result = cli_runner.invoke(cli_main, "--help")
    assert result.exit_code == os.EX_OK, _format_cli_error(result)

    result = cli_runner.invoke(cli_main, "--version")
    assert result.exit_code == os.EX_OK, _format_cli_error(result)
    assert result.stdout.strip() == API_VERSION


def test_echo_dotenv(cli_runner: CliRunner, monkeypatch: pytest.MonkeyPatch):
    # simcore-service-dynamic-scheduler echo-dotenv
    result = cli_runner.invoke(cli_main, "echo-dotenv")
    assert result.exit_code == os.EX_OK, _format_cli_error(result)

    environs = load_dotenv(result.stdout)

    with monkeypatch.context() as patch:
        setenvs_from_dict(patch, environs)
        ApplicationSettings.create_from_envs()


def test_list_settings(
    cli_runner: CliRunner, app_environment: EnvVarsDict, monkeypatch: pytest.MonkeyPatch
):
    with monkeypatch.context() as patch:
        setenvs_from_dict(
            patch,
            {
                **app_environment,
                "DYNAMIC_SCHEDULER_TRACING": "{}",
                "TRACING_OPENTELEMETRY_COLLECTOR_ENDPOINT": "http://replace-with-opentelemetry-collector",
                "TRACING_OPENTELEMETRY_COLLECTOR_PORT": "4318",
            },
        )

        # simcore-service-dynamic-scheduler settings --show-secrets --as-json
        result = cli_runner.invoke(
            cli_main, ["settings", "--show-secrets", "--as-json"]
        )
        assert result.exit_code == os.EX_OK, _format_cli_error(result)

    print(result.output)
    settings = ApplicationSettings(result.output)
    assert settings.model_dump() == ApplicationSettings.create_from_envs().model_dump()


def test_main(app_environment: EnvVarsDict):
    from simcore_service_dynamic_scheduler.main import the_app

    assert the_app
