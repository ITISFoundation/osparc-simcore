# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import os

from pytest_simcore.helpers.typing_env import EnvVarsDict
from simcore_service_dask_sidecar._meta import API_VERSION
from simcore_service_dask_sidecar.cli import main
from simcore_service_dask_sidecar.settings import Settings
from typer.testing import CliRunner


def test_cli_help_and_version(cli_runner: CliRunner):
    # invitations-maker --help
    result = cli_runner.invoke(main, "--help")
    assert result.exit_code == os.EX_OK, result.output

    result = cli_runner.invoke(main, "--version")
    assert result.exit_code == os.EX_OK, result.output
    assert result.stdout.strip() == API_VERSION


def test_list_settings(cli_runner: CliRunner, app_environment: EnvVarsDict):
    result = cli_runner.invoke(main, ["settings", "--show-secrets", "--as-json"])
    assert result.exit_code == os.EX_OK, result.output

    settings = Settings(result.output)
    assert settings.model_dump() == Settings.create_from_envs().model_dump()
