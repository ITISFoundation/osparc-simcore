# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import os
import traceback

from click.testing import Result
from pytest_simcore.helpers.typing_env import EnvVarsDict
from simcore_service_dask_sidecar._meta import API_VERSION
from simcore_service_dask_sidecar.cli import main
from simcore_service_dask_sidecar.settings import Settings
from typer.testing import CliRunner


def _format_cli_error(result: Result) -> str:
    assert result.exception
    tb_message = "\n".join(traceback.format_tb(result.exception.__traceback__))
    return tb_message


def test_cli_help_and_version(cli_runner: CliRunner):
    # invitations-maker --help
    result = cli_runner.invoke(main, "--help")
    assert result.exit_code == os.EX_OK, _format_cli_error(result)

    result = cli_runner.invoke(main, "--version")
    assert result.exit_code == os.EX_OK, _format_cli_error(result)
    assert result.stdout.strip() == API_VERSION


def test_list_settings(cli_runner: CliRunner, app_environment: EnvVarsDict):
    result = cli_runner.invoke(main, ["settings", "--show-secrets", "--as-json"])
    assert result.exit_code == os.EX_OK, _format_cli_error(result)

    print(result.output)
    settings = Settings.parse_raw(result.output)
    assert settings == Settings.create_from_envs()
