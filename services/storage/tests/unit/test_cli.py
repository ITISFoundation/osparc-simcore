# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import contextlib
import json
import os
from io import StringIO

import pytest
from dotenv import dotenv_values
from simcore_service_storage.cli import main
from simcore_service_storage.settings import Settings
from typer.testing import CliRunner


@pytest.mark.parametrize(
    "arguments", ["--help", "run --help".split(), "settings --help".split()]
)
def test_cli_help(arguments: list[str] | str, cli_runner: CliRunner):
    result = cli_runner.invoke(main, arguments)
    assert result.exit_code == os.EX_OK, result


def test_cli_settings_as_json(
    project_env_devel_environment: None, cli_runner: CliRunner
):
    result = cli_runner.invoke(main, ["settings", "--as-json"])
    assert result.exit_code == os.EX_OK, result
    # reuse resulting json to build settings
    settings: dict = json.loads(result.stdout)
    assert Settings(settings)


def test_cli_settings_env_file(
    project_env_devel_environment: None, cli_runner: CliRunner
):
    result = cli_runner.invoke(main, ["settings", "--compact"])
    assert result.exit_code == os.EX_OK, result

    # reuse resulting env_file to build settings
    env_file = StringIO(result.stdout)

    settings = dotenv_values(stream=env_file)
    for key, value in settings.items():
        with contextlib.suppress(json.decoder.JSONDecodeError):
            settings[key] = json.loads(str(value))

    assert Settings(settings)
