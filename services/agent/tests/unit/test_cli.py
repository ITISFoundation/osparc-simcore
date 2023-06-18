# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

import traceback

import pytest
from click.testing import Result
from simcore_service_agent.cli import main
from typer.testing import CliRunner


@pytest.fixture
def cli_runner() -> CliRunner:
    return CliRunner()


def _format_cli_error(result: Result) -> str:
    assert result.exception
    tb_message = "\n".join(traceback.format_tb(result.exception.__traceback__))
    return f"Below exception was raised by the cli:\n{tb_message}"


def test_process_cli_options(env: None, cli_runner: CliRunner):
    result = cli_runner.invoke(main, ["--help"])
    print(result.stdout)
    assert result.exit_code == 0, _format_cli_error(result)

    result = cli_runner.invoke(main, ["settings"])
    print(result.stdout)
    assert result.exit_code == 0, _format_cli_error(result)

    result = cli_runner.invoke(main, ["--version"])
    print(result.stdout)
    assert result.exit_code == 0, _format_cli_error(result)
