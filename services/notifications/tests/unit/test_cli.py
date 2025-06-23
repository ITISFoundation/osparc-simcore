# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

import traceback

import pytest
from click.testing import Result
from pytest_simcore.helpers.monkeypatch_envs import (
    EnvVarsDict,
    load_dotenv,
    setenvs_from_dict,
)
from simcore_service_notifications.cli import main
from simcore_service_notifications.core.settings import ApplicationSettings
from typer.testing import CliRunner

pytest_simcore_core_services_selection = [
    "postgres",
    "rabbit",
]


@pytest.fixture
def cli_runner(app_environment: EnvVarsDict) -> CliRunner:
    return CliRunner()


def _format_cli_error(result: Result) -> str:
    assert result.exception
    tb_message = "\n".join(traceback.format_tb(result.exception.__traceback__))
    return f"Below exception was raised by the cli:\n{tb_message}"


async def test_process_cli_options(cli_runner: CliRunner):
    result = cli_runner.invoke(main, ["--help"])
    print(result.stdout)
    assert result.exit_code == 0, _format_cli_error(result)

    result = cli_runner.invoke(main, ["settings"])
    print(result.stdout)
    assert result.exit_code == 0, _format_cli_error(result)

    result = cli_runner.invoke(main, ["--version"])
    print(result.stdout)
    assert result.exit_code == 0, _format_cli_error(result)


async def test_echo_dotenv(cli_runner: CliRunner, monkeypatch: pytest.MonkeyPatch):
    result = cli_runner.invoke(main, ["echo-dotenv"])
    print(result.stdout)
    assert result.exit_code == 0, _format_cli_error(result)

    environs = load_dotenv(result.stdout)

    with monkeypatch.context() as patch:
        setenvs_from_dict(patch, environs)
        assert ApplicationSettings.create_from_envs()
